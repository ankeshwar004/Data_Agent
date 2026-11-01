"""Command-line entry point for offline and live evaluation modes."""

from __future__ import annotations

import argparse
import json

from .cases import load_cases, summarize
from .live import evaluate_live
from .offline import evaluate, run_case


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate baseline and autonomous financial workflows."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use production PostgreSQL, FMP, and OpenRouter services.",
    )
    args = parser.parse_args()
    try:
        report = (
            evaluate_live(load_cases(expand=False))
            if args.live
            else evaluate(load_cases())
        )
    except RuntimeError as error:
        parser.error(str(error))

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    elif args.live:
        print(
            f"Live evaluation: {report['success_rate']:.1f}% "
            f"({report['measured_cases']} measured, "
            f"{report['skipped_cases']} skipped)"
        )
    else:
        print("Workflow              Financial success   Failure handling")
        for name in ("baseline", "autonomous"):
            item = report[name]
            print(
                f"{name:22} {item['task_completion_success_rate']:6.1f}% "
                f"({item['successful_financial_tasks']}/{item['financial_cases']})"
                f"       {item['failure_handling_rate']:6.1f}% "
                f"({item['handled_failures']}/{item['failure_cases']})"
            )
        print(
            f"Improvement: {report['improvement']['successful_tasks']} tasks, "
            f"{report['improvement']['percentage_points']:+.1f} percentage points"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
