"""Deterministic offline evaluation using fixed FMP-like fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .cases import compare_reports, summarize


@dataclass
class Store:
    records: dict[tuple[str, int, str], float] = field(default_factory=dict)

    def has(self, case: dict[str, Any]) -> bool:
        return (case["ticker"], case["year"], case["metric"]) in self.records

    def load(self, case: dict[str, Any]) -> None:
        if case.get("failure") == "load_error":
            raise RuntimeError("simulated database load failure")
        record = case["fmp_record"]
        if record.get("period") != "FY":
            return
        self.records[
            (case["ticker"], int(record["fiscalYear"]), case["metric"])
        ] = record[case["metric"]]

    def value(self, case: dict[str, Any]) -> float | None:
        return self.records.get((case["ticker"], case["year"], case["metric"]))


@dataclass
class FixtureFMP:
    case: dict[str, Any]
    calls: int = 0

    def fetch(self) -> dict[str, Any]:
        self.calls += 1
        if self.case.get("failure") in {
            "timeout",
            "invalid_response",
            "empty_response",
        }:
            raise RuntimeError(f"simulated FMP {self.case['failure']}")
        return self.case["fmp_record"]


def _query(store: Store, case: dict[str, Any]) -> float | None:
    if case.get("failure") == "sql_error":
        raise RuntimeError("simulated SQL execution failure")
    return store.value(case)


def _initial_store(case: dict[str, Any]) -> Store:
    store = Store()
    if case["group"] == "data_exists":
        store.records[(case["ticker"], case["year"], case["metric"])] = case["value"]
    return store


def run_case(case: dict[str, Any], autonomous: bool) -> dict[str, Any]:
    """Run one case without external services."""
    store = _initial_store(case)
    fmp = FixtureFMP(case)
    max_attempts = 3 if autonomous else 1
    error = None
    initial_coverage = store.has(case)

    for _ in range(max_attempts):
        if store.has(case):
            break
        try:
            store.load({**case, "fmp_record": fmp.fetch()})
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            error = str(exc)
            if not autonomous:
                break

    query_executed = False
    sql_attempted = case.get("failure") in {None, "sql_error"}
    try:
        value = _query(store, case)
        query_executed = True
    except RuntimeError as exc:
        value = None
        error = str(exc)

    if case["group"] == "failure":
        passed = value is None and error is not None and fmp.calls <= max_attempts
        answer = (
            f"Unable to retrieve {case['ticker']} {case['year']}: {error}"
            if error
            else ""
        )
    else:
        passed = (
            value is not None
            and abs(value - case["value"]) <= 0.01
            and query_executed
            and (initial_coverage or store.has(case))
        )
        answer = (
            f"{case['ticker']} {case['metric']} for {case['year']}: {value}"
            if value is not None
            else ""
        )
    return {
        "id": case["id"],
        "group": case["group"],
        "passed": passed,
        "answer": answer,
        "loaded": store.has(case),
        "initial_coverage": initial_coverage,
        "query_executed": query_executed,
        "sql_attempted": sql_attempted,
        "sql_attempt_results": [query_executed] if sql_attempted else [],
        "first_attempt_sql_success": query_executed if sql_attempted else None,
        "final_sql_success": query_executed if sql_attempted else None,
        "answer_grounded": query_executed and value is not None,
        "fmp_calls": fmp.calls,
        "error": error,
        "etl_complete": case["group"] != "data_missing" or store.has(case),
        "records_expected": 1 if case["group"] == "data_missing" else 0,
        "records_loaded": 1 if case["group"] == "data_missing" and store.has(case) else 0,
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the one-attempt baseline with bounded autonomous retries."""
    baseline = summarize([run_case(case, autonomous=False) for case in cases])
    autonomous = summarize([run_case(case, autonomous=True) for case in cases])
    return {
        "baseline": baseline,
        "autonomous": autonomous,
        "improvement": compare_reports(baseline, autonomous),
    }
