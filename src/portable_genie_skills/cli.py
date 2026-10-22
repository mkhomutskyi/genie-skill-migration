"""Command-line interface for portable skill tooling."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from portable_genie_skills.core import (
    PRODUCTS,
    RUNTIMES,
    adapt_skill,
    check_skill,
    scan_path,
    validate_skill,
)
from portable_genie_skills.models import Report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portable-skills",
        description="Check, validate and adapt Agent Skills packages for Databricks Genie.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser(
        "check",
        help="Check a third-party skill for one Genie product: blockers and review items.",
    )
    check.add_argument("path", type=Path)
    check.add_argument("--product", choices=PRODUCTS, required=True)

    adapt = subparsers.add_parser("adapt", help="Validate and adapt a skill package.")
    adapt.add_argument("source", type=Path)
    adapt.add_argument("destination", type=Path)
    adapt.add_argument(
        "--source-runtime",
        choices=sorted(RUNTIMES),
        required=True,
    )
    adapt.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Write a deterministic Markdown report, or JSON when the suffix is .json.",
    )

    validate = subparsers.add_parser(
        "validate",
        help="Strictly validate your own skill package before you publish it.",
    )
    validate.add_argument("path", type=Path)

    scan = subparsers.add_parser("scan", help="Scan a path for unsafe or private content.")
    scan.add_argument("path", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        report = check_skill(args.path, args.product)
    elif args.command == "adapt":
        report = adapt_skill(
            args.source,
            args.destination,
            args.source_runtime,
            report_path=args.report,
        )
        if not any(finding.code == "report.path-overlap" for finding in report.blockers):
            try:
                report.write(args.report)
            except OSError as exc:
                print(f"portable-skills: could not write report: {exc}", file=sys.stderr)
                return 2
    elif args.command == "validate":
        report = validate_skill(args.path)
    else:
        report = scan_path(args.path)
    _print_report(report)
    return 0 if report.ok else 1


def _print_report(report: Report) -> None:
    sys.stdout.write(report.to_json())


if __name__ == "__main__":
    raise SystemExit(main())
