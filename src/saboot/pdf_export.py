"""Minimal dependency-free PDF export for the appeal and evidence pack."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .appeal import AppealDraft
from .audit import AuditResult
from .schema import format_inr, iso_dt

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
FONT_SIZE = 9.5
LINE_HEIGHT = 13
MARGIN = 46
LINES_PER_PAGE = int((PAGE_HEIGHT - 2 * MARGIN) // LINE_HEIGHT)


def _pdf_text(text: str) -> str:
    replacements = {
        "₹": "Rs. ",
        "×": "x",
        "—": "-",
        "–": "-",
        "→": "->",
        "“": '"',
        "”": '"',
        "’": "'",
        "…": "...",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _escape(text: str) -> str:
    text = _pdf_text(text)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int = 92) -> list[str]:
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(word) > width:
            if current:
                lines.append(current)
                current = ""
            for i in range(0, len(word), width):
                lines.append(word[i : i + width])
            continue
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _add(lines: list[str], text: str = "", width: int = 92) -> None:
    lines.extend(_wrap(text, width))


def build_appeal_lines(appeal: AppealDraft, audit: AuditResult) -> list[str]:
    claims = [c for c in audit.claims if c.claim_id in set(appeal.claim_ids)]
    meta = audit.statement.meta
    lines: list[str] = []
    _add(lines, "SABOOT — REQUEST FOR REVIEW")
    _add(lines, "Proof for every rupee.")
    _add(lines, "")
    _add(lines, f"Statement: {meta.statement_id}")
    _add(lines, f"Worker: {meta.worker_id}")
    _add(lines, f"Platform: {meta.platform} (fictional demo platform)")
    _add(lines, f"Period: {meta.period_start.date().isoformat()} to {meta.period_end.date().isoformat()}")
    _add(lines, f"Generated: {iso_dt(appeal.generated_at)}")
    _add(lines, f"Draft provider: {appeal.provider}")
    _add(lines, f"Total requested for review: {format_inr(appeal.total_amount)}")
    _add(lines, f"Verifier: {'PASS' if appeal.verification['passed'] else 'FAIL'}")
    _add(lines, "")
    _add(lines, "APPEAL")
    _add(lines, "")
    _add(lines, f"Subject: {appeal.subject}")
    _add(lines, "")
    for line in appeal.body.splitlines():
        _add(lines, line)
    _add(lines, "")
    _add(lines, "EVIDENCE APPENDIX")
    _add(lines, "")
    for claim in claims:
        _add(lines, f"{claim.claim_id} — {claim.claim_type.replace('_', ' ').title()} — {format_inr(claim.amount)}")
        _add(lines, f"Status: {claim.status} | Confidence: {claim.confidence:.2f}")
        if claim.order_ids:
            _add(lines, f"Orders: {', '.join(claim.order_ids)}")
        if claim.deduction_ids:
            _add(lines, f"Deductions: {', '.join(claim.deduction_ids)}")
        if claim.incentive_ids:
            _add(lines, f"Incentives: {', '.join(claim.incentive_ids)}")
        quote = claim.evidence.get("quote")
        if quote:
            _add(lines, f'Source quote: "{quote}"')
        arithmetic = claim.evidence.get("arithmetic")
        if arithmetic:
            _add(lines, f"Arithmetic: {arithmetic}")
        clause = claim.policy_clause
        if clause:
            _add(lines, f"Policy: {clause.get('id')} — {clause.get('title', '')}")
            _add(lines, f"Source: {clause.get('source_url')}")
            _add(lines, f"Effective: {clause.get('effective_from')} to {clause.get('effective_to')}")
        _add(lines, "")
    _add(lines, "POLICY CITATIONS")
    _add(lines, "")
    for citation in appeal.citations:
        _add(lines, f"{citation['id']} — {citation['title']}")
        _add(lines, f"  {citation['source_url']}")
        _add(lines, f"  Effective {citation.get('effective_from')} to {citation.get('effective_to')}")
    _add(lines, "")
    _add(lines, "HUMAN APPROVAL")
    _add(lines, "")
    _add(lines, f"Approved at: {appeal.approved_at or 'not approved'}")
    _add(lines, "No appeal is sent automatically. This pack is a request for review, not legal advice.")
    _add(lines, "Synthetic demo data; QuickDrop is a fictional platform.")
    return lines


def _content_stream(lines: list[str]) -> str:
    body = [
        "BT",
        f"/F1 {FONT_SIZE} Tf",
        f"{MARGIN} {PAGE_HEIGHT - MARGIN - FONT_SIZE} Td",
        f"{LINE_HEIGHT} TL",
    ]
    for line in lines:
        body.append(f"({_escape(line)}) Tj")
        body.append("T*")
    body.append("ET")
    return "\n".join(body)


def write_text_pdf(lines: Iterable[str], output: str | Path) -> Path:
    lines = list(lines)
    pages = [lines[i : i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)] or [[]]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    objects: list[bytes] = []
    page_ids: list[int] = []
    content_ids: list[int] = []
    next_id = 4
    for _ in pages:
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        next_id += 2

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_lines, page_id, content_id in zip(pages, page_ids, content_ids):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        stream = _content_stream(page_lines).encode("latin-1")
        objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )

    with output.open("wb") as handle:
        handle.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(handle.tell())
            handle.write(f"{index} 0 obj\n".encode("ascii"))
            handle.write(obj)
            handle.write(b"\nendobj\n")
        xref_start = handle.tell()
        handle.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        handle.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            handle.write(f"{offset:010d} 00000 n \n".encode("ascii"))
        handle.write(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_start}\n%%EOF\n"
            ).encode("ascii")
        )
    return output


def export_appeal_pdf(appeal: AppealDraft, audit: AuditResult, output: str | Path) -> Path:
    return write_text_pdf(build_appeal_lines(appeal, audit), output)
