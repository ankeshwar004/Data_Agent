"""
eval/ablation.py
================
Runs two back-to-back eval passes and prints a side-by-side comparison.

Ablation A:  schema WITH sample rows   (include_sample_data=True  — default)
Ablation B:  schema WITHOUT sample rows (include_sample_data=False)

How it works
------------
The generate_sql_query node in sql_agent.py already skips sample data on
retries (when prompt_query_context is non-empty).  For the ablation we want
to *force* include_sample_data=False even on the first attempt.

We achieve this by monkey-patching the module-level flag
ABLATION_FORCE_NO_SAMPLES in agents.sql_agent before each run.  The
generate_sql_query function checks this flag (see the small shim added below).

Note: both runs share the same DB and schema cache, so only the LLM prompt
changes between them.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agents.sql_agent as sql_agent_mod  # noqa: E402
from database.connection import db_connection  # noqa: E402
from eval.runner import run_eval  # noqa: E402
from eval.report import print_report, print_summary, save_json, save_markdown, to_dict  # noqa: E402

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("eval/results")


def compare_reports(report_a: object, report_b: object) -> None:
    """Print a concise side-by-side metric comparison."""

    def row(label: str, a: float, b: float, higher_is_better: bool = True) -> str:
        diff = b - a
        arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "=")
        winner = ""
        if abs(diff) > 0.005:
            winner = "(B better)" if (diff > 0) == higher_is_better else "(A better)"
        return f"  {label:<35} A={a*100:5.1f}%  B={b*100:5.1f}%  {arrow} {diff*100:+.1f}pp  {winner}"

    def row_f(label: str, a: float, b: float, unit: str = "", lower_is_better: bool = False) -> str:
        diff = b - a
        arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "=")
        winner = ""
        if abs(diff) > 0.01:
            is_b_better = (diff < 0) if lower_is_better else (diff > 0)
            winner = "(B better)" if is_b_better else "(A better)"
        return f"  {label:<35} A={a:.2f}{unit}  B={b:.2f}{unit}  {arrow} {diff:+.2f}{unit}  {winner}"

    print("\n" + "=" * 70)
    print("  ABLATION COMPARISON")
    print(f"  A = {report_a.ablation_label}")
    print(f"  B = {report_b.ablation_label}")
    print("=" * 70)
    print(row("SQL execution rate", report_a.sql_exec_rate, report_b.sql_exec_rate))
    print(row("Result accuracy", report_a.result_accuracy, report_b.result_accuracy))
    print(row("Answer accuracy", report_a.answer_accuracy, report_b.answer_accuracy))
    print(row("Refusal accuracy", report_a.refusal_accuracy, report_b.refusal_accuracy))
    print(row_f("Avg SQL attempts", report_a.avg_sql_attempts, report_b.avg_sql_attempts, lower_is_better=True))
    print(row_f("Avg latency", report_a.avg_latency, report_b.avg_latency, unit="s", lower_is_better=True))
    print("=" * 70 + "\n")


def run_ablation() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    db_connection.init_db()
    try:
        # ── Ablation A: WITH sample data (default behaviour) ──────────────
        logger.info("\n\n>>> ABLATION A: with sample rows in schema prompt <<<\n")
        sql_agent_mod.ABLATION_FORCE_NO_SAMPLES = False
        report_a = run_eval(ablation_label="with_samples")
        print_report(report_a)
        save_json(report_a, OUTPUT_DIR / "ablation_with_samples.json")
        save_markdown(report_a, OUTPUT_DIR / "ablation_with_samples.md")

        # Clear the schema cache so Ablation B gets a fresh prompt
        from database.database import DatabaseUtils
        DatabaseUtils._schema_cache.clear()

        # ── Ablation B: WITHOUT sample data ───────────────────────────────
        logger.info("\n\n>>> ABLATION B: without sample rows in schema prompt <<<\n")
        sql_agent_mod.ABLATION_FORCE_NO_SAMPLES = True
        report_b = run_eval(ablation_label="no_samples")
        print_report(report_b)
        save_json(report_b, OUTPUT_DIR / "ablation_no_samples.json")
        save_markdown(report_b, OUTPUT_DIR / "ablation_no_samples.md")

        # ── Side-by-side comparison ───────────────────────────────────────
        compare_reports(report_a, report_b)

    finally:
        sql_agent_mod.ABLATION_FORCE_NO_SAMPLES = False  # reset
        db_connection.close_db()


if __name__ == "__main__":
    run_ablation()

