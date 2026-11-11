"""Saboot command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .audit import audit_statement
from .ingestion import read_bundle, read_pdf
from .policy import PolicyBook
from .render import to_json, to_markdown
from .schema import SabootError, ValidationError, format_inr


def _default_policy_path() -> Path:
    candidates = [
        Path.cwd() / "data" / "policy" / "quickdrop_policy.json",
        Path(__file__).resolve().parents[2] / "data" / "policy" / "quickdrop_policy.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="saboot",
        description="Audit a QuickDrop payout statement and produce evidence-backed claims.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Audit one statement bundle or text PDF")
    source = audit.add_mutually_exclusive_group(required=True)
    source.add_argument("--bundle", help="Directory or zip containing the CSV bundle")
    source.add_argument("--pdf", help="Line-oriented QuickDrop text PDF")
    audit.add_argument(
        "--policy",
        default=None,
        help="Path to the policy JSON (defaults to data/policy/quickdrop_policy.json)",
    )
    audit.add_argument(
        "--out",
        default=None,
        help="Output directory (defaults to proof/<input-name>)",
    )
    audit.add_argument(
        "--format",
        choices=("both", "json", "markdown"),
        default="both",
        help="Output format (default: both)",
    )
    audit.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if verification fails or any item needs human review",
    )
    audit.add_argument("--quiet", action="store_true", help="Only print errors")
    return parser


def _default_out(source: str) -> Path:
    path = Path(source)
    name = path.parent.name if path.name == "statement" else path.stem
    return Path("proof") / name


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "audit":
        parser.error("unknown command")

    source = args.bundle or args.pdf
    out_dir = Path(args.out) if args.out else _default_out(source)
    policy_path = Path(args.policy) if args.policy else _default_policy_path()

    try:
        policy = PolicyBook.load(policy_path)
        if args.bundle:
            statement = read_bundle(args.bundle)
            source_kind = "csv_bundle"
        else:
            statement = read_pdf(args.pdf)
            source_kind = "text_pdf"
        result = audit_statement(statement, policy)
    except ValidationError as exc:
        print(f"Saboot input error: {exc}", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    except SabootError as exc:
        print(f"Saboot error: {exc}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if args.format in ("both", "json"):
        json_path = out_dir / "audit.json"
        json_path.write_text(to_json(result), encoding="utf-8")
        written.append(json_path)
    if args.format in ("both", "markdown"):
        md_path = out_dir / "audit.md"
        md_path.write_text(to_markdown(result), encoding="utf-8")
        written.append(md_path)

    summary = result.summary()
    if not args.quiet:
        print(f"Saboot audit: {result.statement.meta.statement_id} ({source_kind})")
        print(
            f"Claims: {summary['claim_count']} | "
            f"Potential: {format_inr(summary['total_potential'])} | "
            f"Ready: {format_inr(summary['total_ready'])} | "
            f"Needs review: {format_inr(summary['total_needs_review'])}"
        )
        print(
            f"Review items: {summary['review_item_count']} | "
            f"Verifier: {'PASS' if summary['verification_passed'] else 'FAIL'}"
        )
        for path in written:
            print(f"Wrote: {path}")

    strict_failure = (
        not summary["verification_passed"]
        or summary["needs_review_count"] > 0
        or summary["review_item_count"] > 0
    )
    if args.strict and strict_failure:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
