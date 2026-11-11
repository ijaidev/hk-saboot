#!/usr/bin/env python3
"""Create a line-oriented text PDF from a CSV bundle.

This is a reproducible stand-in for a QuickDrop PDF export. It is a text PDF,
not a scan; OCR is explicitly out of scope for the M0-M2 checkpoint.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Iterable

PAGE_WIDTH = 792
PAGE_HEIGHT = 612
FONT_SIZE = 3.8
LINE_HEIGHT = 5.5
MARGIN = 20
LINES_PER_PAGE = int((PAGE_HEIGHT - 2 * MARGIN) // LINE_HEIGHT)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _bundle_lines(bundle: Path) -> list[str]:
    lines: list[str] = []
    for record_type, filename in (
        ("meta", "meta.csv"),
        ("order", "orders.csv"),
        ("earning", "earnings.csv"),
        ("deduction", "deductions.csv"),
        ("incentive", "incentives.csv"),
    ):
        path = bundle / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                continue
            for row in reader:
                if not any(str(v).strip() for v in row.values() if v is not None):
                    continue
                parts = [record_type]
                for key, value in row.items():
                    if key is None:
                        continue
                    text = str(value).strip()
                    if text:
                        parts.append(f"{key.strip()}={text}")
                lines.append("|".join(parts))
    return lines


def _content_stream(lines: list[str]) -> str:
    body = ["BT", f"/F1 {FONT_SIZE} Tf", f"{MARGIN} {PAGE_HEIGHT - MARGIN - FONT_SIZE} Td", f"{LINE_HEIGHT} TL"]
    for line in lines:
        body.append(f"({_escape(line)}) Tj")
        body.append("T*")
    body.append("ET")
    return "\n".join(body)


def write_pdf(lines: Iterable[str], output: Path) -> None:
    lines = list(lines)
    pages = [lines[i : i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)] or [[]]

    objects: list[bytes] = []
    # 1: catalog, 2: pages, 3: font, then page/content pairs.
    page_object_ids = []
    content_object_ids = []
    next_id = 4
    for _ in pages:
        page_object_ids.append(next_id)
        content_object_ids.append(next_id + 1)
        next_id += 2

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_object_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    for page_lines, page_id, content_id in zip(pages, page_object_ids, content_object_ids):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        stream = _content_stream(page_lines)
        stream_bytes = stream.encode("latin-1")
        objects.append(
            b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" + stream_bytes + b"\nendstream"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
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


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: make_pdf.py <bundle-dir> <output.pdf>", file=sys.stderr)
        return 2
    bundle = Path(argv[1])
    output = Path(argv[2])
    lines = _bundle_lines(bundle)
    if not lines:
        print(f"no records found in {bundle}", file=sys.stderr)
        return 1
    write_pdf(lines, output)
    print(f"Wrote {len(lines)} records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
