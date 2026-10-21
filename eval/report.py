"""
eval/report.py
==============
Renders an EvalReport as:
  1. A rich terminal table (via tabulate if available, else plain text)
  2. A JSON file for further analysis / diffing between ablation runs
  3. A Markdown summary suitable for pasting into docs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eval.runner import EvalReport

try:
    from tabulate import tabulate
    _HAS_TABULATE = True
except ImportError:
    _HAS_TABULATE = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _fmt(v: float | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.3f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.3f}M"
    return f"{v:.4f}"


def _tick(b: bool) -> str:
    return "✓" if b else "✗"


# ── Terminal output ────────────────────────────────────────────────────────────

def print_positive_table(report: "EvalReport") -> None:
    rows = []
    for r in report.positive_results:
        rows.append([
            r.case_id,
            r.ticker,
            r.year or "—",
            r.category,
            _fmt(r.gold_value),
            _tick(r.sql_execution_success),
            _tick(r.result_match),
            _tick(r.answer_match),
            r.sql_attempts,
            f"{r.latency_s:.1f}s",
            "NO DATA" if not r.gold_available else "",
        ])

    headers = [
        "Case ID", "Ticker", "Year", "Category",
        "Gold Value", "SQL OK", "Result≈", "Answer≈",
        "Attempts", "Latency", "Note",
    ]

    if _HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        print("\t".join(headers))
        for row in rows:
            print("\t".join(str(c) for c in row))


def print_negative_table(report: "EvalReport") -> None:
    rows = []
    for r in report.negative_results:
        rows.append([
            r.case_id,
            r.expected_behavior,
            _tick(r.refuse_ok),
            _tick(r.sql_execution_success),
            f"{r.latency_s:.1f}s",
            (r.agent_final_answer[:60] + "…") if len(r.agent_final_answer) > 60 else r.agent_final_answer,
        ])

    headers = ["Case ID", "Expected", "Refuse OK", "SQL Ran", "Latency", "Answer (truncated)"]

    if _HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        print("\t".join(headers))
        for row in rows:
            print("\t".join(str(c) for c in row))


def print_summary(report: "EvalReport") -> None:
    print(f"\n{'=' * 60}")
    print(f"  EVAL SUMMARY  —  ablation: {report.ablation_label}")
    print(f"{'=' * 60}")
    print(f"  Positive cases        : {len(report.positive_results)}")
    print(f"  Negative cases        : {len(report.negative_results)}")
    print(f"  Gold data available   : {sum(r.gold_available for r in report.positive_results)}")
    print()
    print(f"  SQL execution rate    : {_pct(report.sql_exec_rate)}")
    print(f"  Result accuracy       : {_pct(report.result_accuracy)}   (sql_result ≈ gold)")
    print(f"  Answer accuracy       : {_pct(report.answer_accuracy)}   (final_answer ≈ gold)")
    print(f"  Refusal accuracy      : {_pct(report.refusal_accuracy)}")
    print()
    print(f"  Avg SQL attempts      : {report.avg_sql_attempts:.2f}")
    print(f"  Avg latency           : {report.avg_latency:.1f}s")
    print(f"{'=' * 60}\n")


def print_report(report: "EvalReport") -> None:
    print(f"\n\n{'#' * 60}")
    print(f"  POSITIVE CASES  —  {report.ablation_label}")
    print(f"{'#' * 60}\n")
    print_positive_table(report)

    print(f"\n\n{'#' * 60}")
    print(f"  NEGATIVE CASES  —  {report.ablation_label}")
    print(f"{'#' * 60}\n")
    print_negative_table(report)

    print_summary(report)


# ── JSON serialization ─────────────────────────────────────────────────────────

def to_dict(report: "EvalReport") -> dict:
    return {
        "ablation_label": report.ablation_label,
        "summary": {
            "sql_exec_rate": report.sql_exec_rate,
            "result_accuracy": report.result_accuracy,
            "answer_accuracy": report.answer_accuracy,
            "refusal_accuracy": report.refusal_accuracy,
            "avg_sql_attempts": report.avg_sql_attempts,
            "avg_latency_s": report.avg_latency,
            "positive_cases": len(report.positive_results),
            "negative_cases": len(report.negative_results),
        },
        "positive": [
            {
                "id": r.case_id,
                "ticker": r.ticker,
                "year": r.year,
                "category": r.category,
                "gold_value": r.gold_value,
                "gold_available": r.gold_available,
                "sql_exec_ok": r.sql_execution_success,
                "result_match": r.result_match,
                "answer_match": r.answer_match,
                "sql_attempts": r.sql_attempts,
                "latency_s": round(r.latency_s, 2),
                "agent_sql": r.agent_sql,
                "agent_answer": r.agent_final_answer,
                "agent_error": r.agent_error,
                "note": r.note,
            }
            for r in report.positive_results
        ],
        "negative": [
            {
                "id": r.case_id,
                "expected_behavior": r.expected_behavior,
                "refuse_ok": r.refuse_ok,
                "sql_ran": r.sql_execution_success,
                "latency_s": round(r.latency_s, 2),
                "agent_answer": r.agent_final_answer,
                "agent_error": r.agent_error,
                "note": r.note,
            }
            for r in report.negative_results
        ],
    }


def save_json(report: "EvalReport", path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(to_dict(report), f, indent=2, default=str)
    print(f"Report saved → {path}")


# ── Markdown ──────────────────────────────────────────────────────────────────

def to_markdown(report: "EvalReport") -> str:
    lines = []
    lines.append(f"# Eval Report — `{report.ablation_label}`\n")

    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| SQL execution rate | {_pct(report.sql_exec_rate)} |")
    lines.append(f"| Result accuracy (sql_result ≈ gold) | {_pct(report.result_accuracy)} |")
    lines.append(f"| Answer accuracy (final_answer ≈ gold) | {_pct(report.answer_accuracy)} |")
    lines.append(f"| Refusal accuracy | {_pct(report.refusal_accuracy)} |")
    lines.append(f"| Avg SQL attempts | {report.avg_sql_attempts:.2f} |")
    lines.append(f"| Avg latency | {report.avg_latency:.1f}s |")
    lines.append(f"| Positive cases | {len(report.positive_results)} |")
    lines.append(f"| Negative cases | {len(report.negative_results)} |\n")

    lines.append("## Positive Cases\n")
    lines.append("| ID | Ticker | Year | Gold | SQL OK | Result≈ | Answer≈ | Attempts | Latency |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in report.positive_results:
        lines.append(
            f"| {r.case_id} | {r.ticker} | {r.year or '—'} "
            f"| {_fmt(r.gold_value)} "
            f"| {_tick(r.sql_execution_success)} "
            f"| {_tick(r.result_match)} "
            f"| {_tick(r.answer_match)} "
            f"| {r.sql_attempts} "
            f"| {r.latency_s:.1f}s |"
        )

    lines.append("\n## Negative Cases\n")
    lines.append("| ID | Expected | Refuse OK | SQL Ran | Latency |")
    lines.append("|---|---|---|---|---|")
    for r in report.negative_results:
        lines.append(
            f"| {r.case_id} | {r.expected_behavior} "
            f"| {_tick(r.refuse_ok)} "
            f"| {_tick(r.sql_execution_success)} "
            f"| {r.latency_s:.1f}s |"
        )

    return "\n".join(lines)


def save_markdown(report: "EvalReport", path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(report))
    print(f"Markdown report saved → {path}")
