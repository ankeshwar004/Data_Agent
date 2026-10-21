"""
eval/__main__.py
================
CLI entry point for the eval harness.

Usage
-----
# Full eval (positive + negative), default ablation label
python -m eval

# Only positive cases
python -m eval --mode positive

# Only negative cases
python -m eval --mode negative

# Run the two-way ablation (with samples vs without samples)
python -m eval --mode ablation

# Save outputs to a specific directory
python -m eval --output-dir eval/results/run_01

# Override ablation label
python -m eval --label my_experiment
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow:  python -m eval  from the project root
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import db_connection  # noqa: E402
from eval.runner import run_eval  # noqa: E402
from eval.report import print_report, save_json, save_markdown  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m eval",
        description="Run the Data Agent evaluation harness.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "positive", "negative", "ablation"],
        default="full",
        help="Which cases to run (default: full).",
    )
    parser.add_argument(
        "--label",
        default="default",
        help="Ablation label embedded in the report.",
    )
    parser.add_argument(
        "--output-dir",
        default="eval/results",
        help="Directory for JSON + Markdown outputs.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "ablation":
        # Delegate entirely to the ablation module
        from eval.ablation import run_ablation
        run_ablation()
        return 0

    db_connection.init_db()
    try:
        run_positive = args.mode in ("full", "positive")
        run_negative = args.mode in ("full", "negative")

        report = run_eval(
            ablation_label=args.label,
            positive_ids=None if run_positive else [],
            negative_ids=None if run_negative else [],
        )

        print_report(report)
        save_json(report, output_dir / f"eval_{args.label}.json")
        save_markdown(report, output_dir / f"eval_{args.label}.md")

    finally:
        db_connection.close_db()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

