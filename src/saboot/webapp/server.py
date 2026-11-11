"""Local-only web server for the Saboot audit UI.

The UI is a single page served from `static/`. It calls the same deterministic
engine used by the CLI. No external services, no deployment, no auto-send.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .. import __version__
from ..appeal import AppealDraft, generate_appeal
from ..audit import AuditResult, audit_statement
from ..ingestion import read_bundle, read_pdf
from ..llm import provider_from_env
from ..pdf_export import export_appeal_pdf
from ..policy import PolicyBook
from ..schema import SabootError, ValidationError
from .risk import compute_risk

REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_POLICY = REPO_ROOT / "data" / "policy" / "quickdrop_policy.json"
DEMO_BUNDLE = REPO_ROOT / "data" / "fixtures" / "golden" / "G12_multiple" / "statement"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_BODY_BYTES = 16 * 1024 * 1024


@dataclass
class Case:
    audit_id: str
    audit: AuditResult
    source_name: str
    created_at: datetime
    approved_claim_ids: set[str] = field(default_factory=set)
    approved_at: str | None = None
    appeal: AppealDraft | None = None


class CaseStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cases: dict[str, Case] = {}

    def put(self, audit: AuditResult, source_name: str) -> Case:
        case = Case(
            audit_id=uuid.uuid4().hex,
            audit=audit,
            source_name=source_name,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._cases[case.audit_id] = case
        return case

    def get(self, audit_id: str) -> Case | None:
        with self._lock:
            return self._cases.get(audit_id)


def audit_payload(case: Case) -> dict[str, Any]:
    payload = case.audit.to_dict()
    payload["audit_id"] = case.audit_id
    payload["source_name"] = case.source_name
    payload["risk"] = compute_risk(payload)
    payload["approval"] = {
        "approved_claim_ids": sorted(case.approved_claim_ids),
        "approved_at": case.approved_at,
    }
    if case.appeal is not None:
        payload["appeal"] = case.appeal.to_dict()
    return payload


class SabootServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], policy: PolicyBook):
        super().__init__(address, SabootHandler)
        self.store = CaseStore()
        self.policy = policy


class SabootHandler(BaseHTTPRequestHandler):
    server_version = "SabootHTTP/0.1"

    @property
    def app(self) -> SabootServer:
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._send_json(status, {"ok": False, "error": message})

    def _read_json(self) -> dict[str, Any] | None:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._error(411, "Content-Length is required")
            return None
        try:
            length = int(raw_length)
        except ValueError:
            self._error(400, "Invalid Content-Length")
            return None
        if length <= 0 or length > MAX_BODY_BYTES:
            self._error(413, "Request body is empty or too large")
            return None
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(400, "Request body must be JSON")
            return None
        if not isinstance(data, dict):
            self._error(400, "Request body must be a JSON object")
            return None
        return data

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._error(404, "Not found")
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _static_path(self, url_path: str) -> Path | None:
        relative = url_path.removeprefix("/static/")
        candidate = (STATIC_DIR / relative).resolve()
        root = STATIC_DIR.resolve()
        if root not in candidate.parents and candidate != root:
            return None
        return candidate

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            provider = provider_from_env()
            self._send_json(
                200,
                {
                    "ok": True,
                    "version": __version__,
                    "engine": "deterministic-v1",
                    "provider": provider.name,
                    "ui": "local",
                },
            )
            return
        if path == "/api/demo":
            try:
                statement = read_bundle(DEMO_BUNDLE)
                audit = audit_statement(statement, self.app.policy)
                case = self.app.store.put(audit, "sample: G12 multiple claims")
            except (SabootError, ValidationError) as exc:
                self._error(500, str(exc))
                return
            self._send_json(200, {"ok": True, "audit_id": case.audit_id, "audit": audit_payload(case)})
            return
        if path in ("/", "/index.html"):
            self._serve_file(STATIC_DIR / "index.html")
            return
        if path.startswith("/static/"):
            static_path = self._static_path(path)
            if static_path is None:
                self._error(404, "Not found")
                return
            self._serve_file(static_path)
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self._error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/audit":
            self._handle_audit()
            return
        if path == "/api/approve":
            self._handle_approve()
            return
        if path == "/api/appeal":
            self._handle_appeal()
            return
        if path == "/api/export":
            self._handle_export()
            return
        self._error(404, "Not found")

    def _handle_audit(self) -> None:
        data = self._read_json()
        if data is None:
            return
        filename = str(data.get("filename", "")).strip()
        kind = str(data.get("kind", "")).strip().lower()
        encoded = data.get("data")
        if not filename or kind not in ("pdf", "zip") or not isinstance(encoded, str):
            self._error(400, "filename, kind (pdf|zip), and base64 data are required")
            return
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            self._error(400, "data is not valid base64")
            return
        if not raw:
            self._error(400, "uploaded file is empty")
            return
        if len(raw) > MAX_UPLOAD_BYTES:
            self._error(413, "uploaded file is larger than 10 MB")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="saboot-upload-") as tmp:
                suffix = ".pdf" if kind == "pdf" else ".zip"
                upload = Path(tmp) / f"statement{suffix}"
                upload.write_bytes(raw)
                if kind == "pdf":
                    statement = read_pdf(upload)
                else:
                    statement = read_bundle(upload)
            audit = audit_statement(statement, self.app.policy)
        except ValidationError as exc:
            self._error(400, f"Input validation failed: {exc}")
            return
        except SabootError as exc:
            self._error(400, str(exc))
            return
        case = self.app.store.put(audit, filename)
        self._send_json(200, {"ok": True, "audit_id": case.audit_id, "audit": audit_payload(case)})

    def _handle_approve(self) -> None:
        data = self._read_json()
        if data is None:
            return
        audit_id = str(data.get("audit_id", ""))
        claim_ids = data.get("claim_ids", [])
        if not isinstance(claim_ids, list) or not claim_ids:
            self._error(400, "claim_ids must be a non-empty list")
            return
        case = self.app.store.get(audit_id)
        if case is None:
            self._error(404, "audit not found")
            return
        by_id = {claim.claim_id: claim for claim in case.audit.claims}
        selected: list[str] = []
        for raw in claim_ids:
            claim_id = str(raw)
            claim = by_id.get(claim_id)
            if claim is None:
                self._error(400, f"unknown claim ID {claim_id}")
                return
            if claim.status != "ready":
                self._error(400, f"claim {claim_id} needs review and cannot be approved")
                return
            selected.append(claim_id)
        case.approved_claim_ids = set(selected)
        case.approved_at = datetime.now(timezone.utc).isoformat()
        case.appeal = None
        self._send_json(200, {"ok": True, "audit": audit_payload(case)})

    def _handle_appeal(self) -> None:
        data = self._read_json()
        if data is None:
            return
        audit_id = str(data.get("audit_id", ""))
        case = self.app.store.get(audit_id)
        if case is None:
            self._error(404, "audit not found")
            return
        if not case.approved_claim_ids:
            self._error(400, "approve at least one claim before generating an appeal")
            return
        try:
            appeal = generate_appeal(
                case.audit,
                sorted(case.approved_claim_ids),
                audit_id=case.audit_id,
                provider=provider_from_env(),
                approved_at=case.approved_at,
            )
        except SabootError as exc:
            self._error(400, str(exc))
            return
        case.appeal = appeal
        self._send_json(200, {"ok": True, "appeal": appeal.to_dict(), "audit": audit_payload(case)})

    def _handle_export(self) -> None:
        data = self._read_json()
        if data is None:
            return
        audit_id = str(data.get("audit_id", ""))
        case = self.app.store.get(audit_id)
        if case is None:
            self._error(404, "audit not found")
            return
        if case.appeal is None:
            self._error(400, "generate an appeal before exporting")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="saboot-pdf-") as tmp:
                pdf_path = Path(tmp) / "saboot-appeal.pdf"
                export_appeal_pdf(case.appeal, case.audit, pdf_path)
                pdf_bytes = pdf_path.read_bytes()
        except Exception as exc:  # pragma: no cover - defensive
            self._error(500, f"PDF export failed: {exc}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf_bytes)))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="saboot-appeal-{case.audit_id[:8]}.pdf"',
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(pdf_bytes)


def make_server(host: str, port: int, policy_path: str | Path = DEFAULT_POLICY) -> SabootServer:
    policy = PolicyBook.load(policy_path)
    return SabootServer((host, port), policy)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="saboot.webapp", description="Local Saboot audit UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port, args.policy)
    url = f"http://{args.host}:{server.server_address[1]}"
    print(f"Saboot local UI: {url}", flush=True)
    print("Template-only appeal path is available with no API key.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
