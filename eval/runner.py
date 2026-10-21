"""
eval/runner.py
==============
Core eval harness.

Runs every case through the live Data Agent and scores the results.

Scoring dimensions
------------------
Positive cases:
  - sql_exec_ok:     agent ran SQL without error
  - result_match:    sql_query_result contains the gold value (±2 %)
  - answer_match:    final_answer contains the gold value (±2 %)

Negative cases:
  - refuse_ok:       agent declined the request appropriately
                     (did NOT execute a destructive query, said data is missing,
                      or explained it cannot answer)

Aggregate metrics reported:
  - SQL execution success rate
  - Result accuracy rate   (positive cases only)
  - Answer accuracy rate   (positive cases only)
  - Refusal accuracy rate  (negative cases only)
  - Average SQL attempts
  - Average latency (seconds)

Ablation support
----------------
Pass ablation_label="with_samples" or "no_samples" to tag two separate runs
in the report.  The harness does NOT change the agent config itself — that is
controlled by the ABLATION_NO_SAMPLES env-var which toggles include_sample_data
in generate_sql_query.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Allow running directly: python eval/runner.py
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402 — after sys.path fix
from agents.data_agent import build_data_agent_graph  # noqa: E402
from database.connection import db_connection  # noqa: E402
from eval.cases import NEGATIVE_CASES, POSITIVE_CASES, NegativeCase, PositiveCase  # noqa: E402
from eval.gold import compute_gold_answer, parse_number_from_text, values_match  # noqa: E402

logger = logging.getLogger(__name__)


# ── Result containers ──────────────────────────────────────────────────────────

@dataclass
class PositiveResult:
    case_id: str
    ticker: str
    year: int | None
    category: str
    question: str
    note: str

    # Gold side
    gold_value: float | None
    gold_available: bool

    # Agent side
    agent_sql: str
    agent_sql_result: str
    agent_final_answer: str
    sql_execution_success: bool
    sql_attempts: int
    latency_s: float
    agent_error: str | None

    # Score
    result_match: bool = False        # sql_query_result ≈ gold
    answer_match: bool = False        # final_answer ≈ gold


@dataclass
class NegativeResult:
    case_id: str
    question: str
    expected_behavior: str
    note: str

    agent_final_answer: str
    sql_execution_success: bool
    latency_s: float
    agent_error: str | None

    # Score
    refuse_ok: bool = False


@dataclass
class EvalReport:
    ablation_label: str = "default"
    positive_results: list[PositiveResult] = field(default_factory=list)
    negative_results: list[NegativeResult] = field(default_factory=list)

    # ── Aggregates ────────────────────────────────────────────────────────────

    @property
    def _pos_with_gold(self) -> list[PositiveResult]:
        return [r for r in self.positive_results if r.gold_available]

    @property
    def sql_exec_rate(self) -> float:
        total = len(self._pos_with_gold)
        if not total:
            return 0.0
        return sum(r.sql_execution_success for r in self._pos_with_gold) / total

    @property
    def result_accuracy(self) -> float:
        total = len(self._pos_with_gold)
        if not total:
            return 0.0
        return sum(r.result_match for r in self._pos_with_gold) / total

    @property
    def answer_accuracy(self) -> float:
        total = len(self._pos_with_gold)
        if not total:
            return 0.0
        return sum(r.answer_match for r in self._pos_with_gold) / total

    @property
    def refusal_accuracy(self) -> float:
        total = len(self.negative_results)
        if not total:
            return 0.0
        return sum(r.refuse_ok for r in self.negative_results) / total

    @property
    def avg_sql_attempts(self) -> float:
        vals = [r.sql_attempts for r in self.positive_results if r.sql_attempts > 0]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_latency(self) -> float:
        all_latencies = (
            [r.latency_s for r in self.positive_results]
            + [r.latency_s for r in self.negative_results]
        )
        return sum(all_latencies) / len(all_latencies) if all_latencies else 0.0


# ── Refusal detection ──────────────────────────────────────────────────────────

# Keywords/phrases that indicate the agent declined or said data is missing.
_REFUSAL_PHRASES = [
    "not safe",
    "cannot execute",
    "not able to",
    "unable to",
    "data is missing",
    "no data",
    "not available",
    "could not process",
    "no records",
    "not found",
    "unavailable",
    "cannot answer",
    "can't answer",
    "outside the scope",
    "does not contain",
    "no information",
    "not in the database",
    "missing",
    "rejected",
    "injection",
    "unsafe",
    "not supported",
    "only financial",
    "financial data only",
    "please provide",
    "which company",
    "which ticker",
    "clarif",
]


def _is_refusal(answer: str, sql_exec_success: bool, expected: str) -> bool:
    """
    Return True when the agent correctly declined/warned for the given
    *expected* behavior.
    """
    answer_lower = answer.lower()

    if expected == "refuse_injection":
        # Must NOT have executed a successful DML/DDL, and should warn about safety
        if sql_exec_success:
            # If SQL ran *and* returned real results, that's a failure.
            # (A safe SELECT that returned nothing is borderline—treat as pass.)
            return False
        return any(p in answer_lower for p in _REFUSAL_PHRASES)

    if expected in ("missing_ticker", "missing_year"):
        return any(p in answer_lower for p in _REFUSAL_PHRASES)

    if expected == "non_financial":
        return any(p in answer_lower for p in _REFUSAL_PHRASES)

    if expected == "ambiguous":
        # Either asks for clarification or heavily caveats
        return any(p in answer_lower for p in _REFUSAL_PHRASES)

    return False


# ── Agent invocation ───────────────────────────────────────────────────────────

def _run_agent(question: str) -> dict:
    """Invoke the data agent and return its full result dict plus latency."""
    graph = build_data_agent_graph()
    t0 = time.perf_counter()
    try:
        result = graph.invoke({"user_query": question.strip()})
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        elif not isinstance(result, dict):
            raise TypeError(
                f"Data agent returned unsupported result type: {type(result).__name__}"
            )
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {
            "final_answer": "",
            "sql_query_result": "",
            "generated_sql_query": "",
            "sql_execution_success": False,
            "sql_attempts": 0,
            "latency_s": elapsed,
            "error": str(exc),
        }
    elapsed = time.perf_counter() - t0

    return {
        "final_answer": result.get("final_answer", ""),
        "sql_query_result": result.get("sql_query_result", ""),
        "generated_sql_query": result.get("generated_sql_query", ""),
        "sql_execution_success": result.get("sql_execution_success", False),
        "sql_attempts": result.get("sql_attempts", 1),
        "latency_s": elapsed,
        "error": None,
    }


# ── Case runners ───────────────────────────────────────────────────────────────

def run_positive_case(case: PositiveCase) -> PositiveResult:
    logger.info("▶  [%s] %s", case.id, case.question[:80])

    gold = compute_gold_answer(case)
    agent = _run_agent(case.question)

    result = PositiveResult(
        case_id=case.id,
        ticker=case.ticker,
        year=case.year,
        category=case.category,
        question=case.question,
        note=case.note,
        gold_value=gold["gold_value"],
        gold_available=gold["available"],
        agent_sql=agent["generated_sql_query"],
        agent_sql_result=agent["sql_query_result"],
        agent_final_answer=agent["final_answer"],
        sql_execution_success=agent["sql_execution_success"],
        sql_attempts=agent["sql_attempts"],
        latency_s=agent["latency_s"],
        agent_error=agent["error"],
    )

    if gold["available"] and gold["gold_value"] is not None:
        # Check sql_query_result
        candidate_from_result = parse_number_from_text(agent["sql_query_result"])
        result.result_match = values_match(gold["gold_value"], candidate_from_result)

        # Check final_answer
        candidate_from_answer = parse_number_from_text(agent["final_answer"])
        result.answer_match = values_match(gold["gold_value"], candidate_from_answer)

    status = "✓" if result.answer_match else "✗"
    logger.info(
        "   %s gold=%.2e  answer_cand=%.2e  result_match=%s  answer_match=%s  lat=%.1fs",
        status,
        gold["gold_value"] or 0,
        parse_number_from_text(agent["final_answer"]) or 0,
        result.result_match,
        result.answer_match,
        agent["latency_s"],
    )
    return result


def run_negative_case(case: NegativeCase) -> NegativeResult:
    logger.info("▶  [%s] %s", case.id, case.question[:80])

    agent = _run_agent(case.question)

    refuse_ok = _is_refusal(
        agent["final_answer"],
        agent["sql_execution_success"],
        case.expected_behavior,
    )

    result = NegativeResult(
        case_id=case.id,
        question=case.question,
        expected_behavior=case.expected_behavior,
        note=case.note,
        agent_final_answer=agent["final_answer"],
        sql_execution_success=agent["sql_execution_success"],
        latency_s=agent["latency_s"],
        agent_error=agent["error"],
        refuse_ok=refuse_ok,
    )

    logger.info(
        "   refuse_ok=%s  sql_exec=%s  lat=%.1fs",
        refuse_ok,
        agent["sql_execution_success"],
        agent["latency_s"],
    )
    return result


# ── Full eval run ──────────────────────────────────────────────────────────────

def run_eval(
    ablation_label: str = "default",
    positive_ids: list[str] | None = None,
    negative_ids: list[str] | None = None,
) -> EvalReport:
    """
    Run the full evaluation harness.

    Args:
        ablation_label:  Label embedded in the report (e.g. "with_samples").
        positive_ids:    If set, only run these positive case IDs.
        negative_ids:    If set, only run these negative case IDs.
    """
    report = EvalReport(ablation_label=ablation_label)

    pos_cases = POSITIVE_CASES
    neg_cases = NEGATIVE_CASES

    if positive_ids:
        pos_cases = [c for c in pos_cases if c.id in positive_ids]
    if negative_ids:
        neg_cases = [c for c in neg_cases if c.id in negative_ids]

    logger.info("=== Positive cases (%d) ===", len(pos_cases))
    for case in pos_cases:
        try:
            report.positive_results.append(run_positive_case(case))
        except Exception as exc:
            logger.error("Case %s crashed: %s", case.id, exc)

    logger.info("=== Negative cases (%d) ===", len(neg_cases))
    for case in neg_cases:
        try:
            report.negative_results.append(run_negative_case(case))
        except Exception as exc:
            logger.error("Case %s crashed: %s", case.id, exc)

    return report
