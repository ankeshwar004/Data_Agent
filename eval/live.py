"""Live evaluation against PostgreSQL, FMP, and the configured LLM."""

from __future__ import annotations

import os
from typing import Any

from .cases import summarize

ORACLE_COLUMNS = {
    "revenue": ("income_statements", "revenue"),
    "net_income": ("income_statements", "net_income"),
    "total_assets": ("balance_sheets", "total_assets"),
    "operating_cash_flow": ("cash_flow_statements", "operating_cash_flow"),
}


def _require_live_configuration() -> None:
    missing = [
        name
        for name in ("EVAL_DATABASE_URL", "FMP_API_KEY", "OPENROUTER_API_KEY")
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(
            "Live evaluation requires dedicated EVAL_DATABASE_URL, FMP_API_KEY, "
            f"and OPENROUTER_API_KEY; missing: {', '.join(missing)}"
        )


def _read_record(table: str, column: str, ticker: str, year: int) -> dict[str, Any] | None:
    from database.connection import db_connection

    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT c.ticker, s.fiscal_year, s.period, s.{column}
                    FROM {table} s
                    JOIN companies c ON c.company_id = s.company_id
                    WHERE c.ticker = %s AND s.fiscal_year = %s AND s.period = 'FY'""",
                (ticker, year),
            )
            return cur.fetchone()


def run_live_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run one question through production and verify it with an SQL oracle."""
    if case["group"] == "failure":
        return {
            "id": case["id"],
            "group": case["group"],
            "status": "skipped",
            "reason": "Fault injection is not performed against live services.",
        }

    from agents.data_agent import build_data_agent_graph

    table, column = ORACLE_COLUMNS[case["metric"]]
    before = _read_record(table, column, case["ticker"], case["year"])
    result = build_data_agent_graph().invoke({"user_query": case["question"]})
    after = _read_record(table, column, case["ticker"], case["year"])

    value = after[column] if after else None
    value_matches = value is not None and abs(float(value) - case["value"]) <= 0.01
    initial_state_valid = (
        (case["group"] == "data_exists" and before is not None)
        or (case["group"] == "data_missing" and before is None)
    )
    loaded_missing_data = case["group"] != "data_missing" or (
        before is None and after is not None
    )
    query_result = result.get("sql_query_result", [])
    sql_attempt_results = result.get("sql_attempt_results", [])
    etl_attempt_results = result.get("etl_attempt_results", [])
    sql_attempted = bool(sql_attempt_results)
    grounded = bool(query_result) and value_matches
    completed = (
        bool(result.get("final_answer", "").strip())
        and result.get("next_action") == "finish"
    )
    passed = (
        initial_state_valid
        and completed
        and value_matches
        and loaded_missing_data
        and grounded
    )
    return {
        "id": case["id"],
        "group": case["group"],
        "status": "passed" if passed else "failed",
        "initial_record_present": before is not None,
        "record_present_after": after is not None,
        "initial_state_valid": initial_state_valid,
        "value_matches_independent_oracle": value_matches,
        "loaded_missing_data": loaded_missing_data,
        "answer_grounded_in_agent_query_result": grounded,
        "completed_without_unhandled_error": completed,
        "sql_attempted": sql_attempted,
        "first_attempt_sql_success": (
            bool(sql_attempt_results and sql_attempt_results[0])
            if sql_attempted
            else None
        ),
        "final_sql_success": (
            bool(sql_attempt_results and sql_attempt_results[-1])
            if sql_attempted
            else None
        ),
        "sql_attempt_results": sql_attempt_results,
        "etl_complete": loaded_missing_data,
        "records_expected": 1 if case["group"] == "data_missing" else 0,
        "records_loaded": 1 if loaded_missing_data and case["group"] == "data_missing" else 0,
        "etl_attempt_results": etl_attempt_results,
        "passed": passed,
        "final_answer": result.get("final_answer", ""),
        "observations": result.get("observations", []),
    }


def evaluate_live(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run live cases; excluded fault cases are explicitly reported."""
    _require_live_configuration()
    os.environ["DATABASE_URL"] = os.environ["EVAL_DATABASE_URL"]

    from database.connection import db_connection

    db_connection.init_db()
    try:
        results = [run_live_case(case) for case in cases]
    finally:
        db_connection.close_db()

    measured = [item for item in results if item["status"] != "skipped"]
    passed = sum(item["status"] == "passed" for item in measured)
    metrics = summarize(measured)
    return {
        "mode": "live",
        "cases": len(results),
        "measured_cases": len(measured),
        "skipped_cases": len(results) - len(measured),
        "success_rate": 100 * passed / len(measured) if measured else 0.0,
        "sql_execution": {
            "first_attempt_success_rate": metrics["sql_first_attempt_success_rate"],
            "final_execution_success_rate": metrics[
                "sql_final_execution_success_rate"
            ],
        },
        "etl_coverage": {
            "complete_request_success_rate": metrics[
                "etl_complete_request_success_rate"
            ],
            "records_loaded_correctly": metrics["etl_records_loaded_correctly"],
        },
        "results": results,
    }
