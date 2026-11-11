"""Web API integration tests against the real local server and engine."""

from __future__ import annotations

import base64
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from saboot.webapp.server import make_server
from tools.make_pdf import _bundle_lines, write_pdf

ROOT = Path(__file__).resolve().parents[1]
G01 = ROOT / "data" / "fixtures" / "golden" / "G01_duplicate" / "statement"
POLICY = ROOT / "data" / "policy" / "quickdrop_policy.json"


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = make_server("127.0.0.1", 0, POLICY)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method: str, path: str, payload: dict | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    def _pdf_base64(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "g01.pdf"
            write_pdf(_bundle_lines(G01), pdf_path)
            return base64.b64encode(pdf_path.read_bytes()).decode("ascii")

    def _zip_base64(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "bundle.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in G01.iterdir():
                    archive.write(path, arcname=path.name)
            return base64.b64encode(zip_path.read_bytes()).decode("ascii")

    def test_health(self) -> None:
        status, body, _ = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["ok"])
        self.assertEqual(data["provider"], "template")

    def test_demo_case(self) -> None:
        status, body, _ = self.request("GET", "/api/demo")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["audit"]["summary"]["claim_count"], 4)
        self.assertEqual(data["audit"]["risk"]["band"], "high")

    def test_pdf_upload_approve_appeal_export(self) -> None:
        status, body, _ = self.request(
            "POST",
            "/api/audit",
            {"filename": "statement.pdf", "kind": "pdf", "data": self._pdf_base64()},
        )
        self.assertEqual(status, 200, body)
        data = json.loads(body)
        self.assertEqual(data["audit"]["summary"]["claim_count"], 1)
        self.assertEqual(data["audit"]["risk"]["score"], 83)
        self.assertIn("2 × LATE", data["audit"]["claims"][0]["evidence"]["quote"])
        audit_id = data["audit_id"]
        claim_id = data["audit"]["claims"][0]["claim_id"]

        status, body, _ = self.request(
            "POST", "/api/approve", {"audit_id": audit_id, "claim_ids": [claim_id]}
        )
        self.assertEqual(status, 200, body)
        approved = json.loads(body)
        self.assertEqual(approved["audit"]["approval"]["approved_claim_ids"], [claim_id])

        status, body, _ = self.request("POST", "/api/appeal", {"audit_id": audit_id})
        self.assertEqual(status, 200, body)
        appeal = json.loads(body)["appeal"]
        self.assertTrue(appeal["verification"]["passed"])
        self.assertEqual(appeal["provider"], "template")
        self.assertIn("QD-DED-001", appeal["body"])

        status, body, headers = self.request("POST", "/api/export", {"audit_id": audit_id})
        self.assertEqual(status, 200, body)
        self.assertEqual(headers.get("Content-Type"), "application/pdf")
        self.assertTrue(body.startswith(b"%PDF-1.4"))

    def test_zip_upload(self) -> None:
        status, body, _ = self.request(
            "POST",
            "/api/audit",
            {"filename": "bundle.zip", "kind": "zip", "data": self._zip_base64()},
        )
        self.assertEqual(status, 200, body)
        data = json.loads(body)
        self.assertEqual(data["audit"]["summary"]["claim_count"], 1)

    def test_unknown_claim_rejected(self) -> None:
        status, body, _ = self.request("GET", "/api/demo")
        audit_id = json.loads(body)["audit_id"]
        status, body, _ = self.request(
            "POST", "/api/approve", {"audit_id": audit_id, "claim_ids": ["C-999"]}
        )
        self.assertEqual(status, 400)
        self.assertIn("unknown claim", json.loads(body)["error"])

    def test_export_before_appeal_rejected(self) -> None:
        status, body, _ = self.request("GET", "/api/demo")
        audit_id = json.loads(body)["audit_id"]
        status, body, _ = self.request("POST", "/api/export", {"audit_id": audit_id})
        self.assertEqual(status, 400)
        self.assertIn("generate an appeal", json.loads(body)["error"])

    def test_unknown_audit_rejected(self) -> None:
        status, body, _ = self.request(
            "POST", "/api/approve", {"audit_id": "nope", "claim_ids": ["C-001"]}
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
