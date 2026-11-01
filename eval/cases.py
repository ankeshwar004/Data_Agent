"""Evaluation case loading and shared scoring helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CASES_PATH = Path(__file__).with_name("cases.json")


def load_cases(
    path: Path = CASES_PATH, *, expand: bool = True
) -> list[dict[str, Any]]:
    """Load the fixed evaluation dataset, optionally expanded to 45 runs."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if len(cases) != 15:
        raise ValueError("The evaluation dataset must contain 15 cases.")
    return cases * 3 if expand else cases


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate separate financial-completion and failure-handling rates."""
    financial = [item for item in results if item["group"] != "failure"]
    failures = [item for item in results if item["group"] == "failure"]
    financial_rate = 100 * sum(item["passed"] for item in financial) / len(financial)
    failure_rate = 100 * sum(item["passed"] for item in failures) / len(failures)
    sql_cases = [item for item in results if item.get("sql_attempted")]
    etl_cases = [item for item in results if item.get("group") == "data_missing"]
    expected_records = sum(item.get("records_expected", 0) for item in etl_cases)
    loaded_records = sum(item.get("records_loaded", 0) for item in etl_cases)
    return {
        "total": len(results),
        "successful_financial_tasks": sum(item["passed"] for item in financial),
        "financial_cases": len(financial),
        "task_completion_success_rate": financial_rate,
        "handled_failures": sum(item["passed"] for item in failures),
        "failure_cases": len(failures),
        "failure_handling_rate": failure_rate,
        "sql_first_attempt_success_rate": _rate(
            [item.get("first_attempt_sql_success", False) for item in sql_cases]
        ),
        "sql_final_execution_success_rate": _rate(
            [item.get("final_sql_success", False) for item in sql_cases]
        ),
        "etl_complete_request_success_rate": _rate(
            [item.get("etl_complete", False) for item in etl_cases]
        ),
        "etl_records_loaded_correctly": {
            "loaded": loaded_records,
            "expected": expected_records,
            "rate": 100 * loaded_records / expected_records if expected_records else 0.0,
        },
    }


def _rate(values: list[bool]) -> float:
    return 100 * sum(values) / len(values) if values else 0.0


def compare_reports(baseline: dict[str, Any], autonomous: dict[str, Any]) -> dict[str, Any]:
    """Report task-count and percentage-point changes between workflows."""
    return {
        "successful_tasks": (
            autonomous["successful_financial_tasks"]
            - baseline["successful_financial_tasks"]
        ),
        "percentage_points": (
            autonomous["task_completion_success_rate"]
            - baseline["task_completion_success_rate"]
        ),
        "failure_handling_percentage_points": (
            autonomous["failure_handling_rate"]
            - baseline["failure_handling_rate"]
        ),
    }
