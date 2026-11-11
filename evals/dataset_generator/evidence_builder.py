from __future__ import annotations

import hashlib
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _evidence_id(operation: str, fact_ids: list[str]) -> str:
    raw = operation + ":" + ":".join(fact_ids)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _make_evidence(
    operation: str,
    facts: list[dict],
    *,
    parameters: dict | None = None,
    question_hint: str,
) -> dict:
    fact_ids = [fact["fact_id"] for fact in facts]
    first = facts[0]
    return {
        "evidence_id": _evidence_id(operation, fact_ids),
        "operation": operation,
        "fact_ids": fact_ids,
        "parameters": parameters or {},
        "ticker": first["ticker"],
        "company": first["company"],
        "fiscal_year": first["fiscal_year"],
        "period": first["period"],
        "currency": first.get("currency"),
        "statements": sorted({fact["statement"] for fact in facts}),
        "metrics": [fact["metric"] for fact in facts],
        "metric_labels": [fact["metric_label"] for fact in facts],
        "question_hint": question_hint,
    }


class EvidenceBuilder:
    """Build compatible, deterministic evidence units from atomic facts."""

    def build(self, facts: list[dict]) -> list[dict]:
        evidence: list[dict] = []

        # Atomic facts remain available for direct retrieval questions.
        for fact in facts:
            evidence.append(_make_evidence(
                "lookup",
                [fact],
                question_hint=(
                    "Ask for the exact value of this metric for this company and period. "
                    "Do not turn it into a yes/no interpretation question."
                ),
            ))

            # Profit/loss is a semantic interpretation of net income, not a new
            # question-type enum. Python determines the interpretation from its sign.
            if fact["statement"] == "income_statement" and fact["metric"] == "net_income":
                evidence.append(_make_evidence(
                    "profitability",
                    [fact],
                    question_hint=(
                        "Ask whether the company reported a net profit or net loss "
                        "for this period, or whether it was profitable."
                    ),
                ))

        by_period: dict[tuple, dict[tuple[str, str], dict]] = defaultdict(dict)
        by_metric: dict[tuple, list[dict]] = defaultdict(list)

        for fact in facts:
            period_key = (
                fact["ticker"],
                str(fact["fiscal_year"]),
                fact["period"],
                fact.get("currency"),
            )
            by_period[period_key][(fact["statement"], fact["metric"])] = fact

            metric_key = (
                fact["ticker"],
                fact["statement"],
                fact["metric"],
                fact["period"],
                fact.get("currency"),
            )
            by_metric[metric_key].append(fact)

        for indexed in by_period.values():
            revenue = indexed.get(("income_statement", "revenue"))
            cost = indexed.get(("income_statement", "cost_of_revenue"))

            if revenue and cost:
                evidence.append(_make_evidence(
                    "gross_profit",
                    [revenue, cost],
                    parameters={
                        "revenue_fact_id": revenue["fact_id"],
                        "cost_fact_id": cost["fact_id"],
                    },
                    question_hint="Ask for gross profit, calculated as revenue minus cost of revenue.",
                ))

                revenue_value = _decimal(revenue.get("value"))
                if revenue_value not in (None, Decimal("0")):
                    evidence.append(_make_evidence(
                        "gross_profit_margin",
                        [revenue, cost],
                        parameters={
                            "revenue_fact_id": revenue["fact_id"],
                            "cost_fact_id": cost["fact_id"],
                            "formula": "(revenue - cost_of_revenue) / revenue * 100",
                        },
                        question_hint="Ask for gross profit margin as a percentage.",
                    ))

            net_income = indexed.get(("income_statement", "net_income"))
            operating_cash_flow = indexed.get(("cash_flow_statement", "operating_cash_flow"))
            if net_income and operating_cash_flow:
                evidence.append(_make_evidence(
                    "cross_statement_comparison",
                    [operating_cash_flow, net_income],
                    parameters={
                        "left_fact_id": operating_cash_flow["fact_id"],
                        "right_fact_id": net_income["fact_id"],
                        "comparator": "greater_than",
                    },
                    question_hint=(
                        "Ask whether operating cash flow was greater than net income "
                        "for the same fiscal period."
                    ),
                ))

        # Same metric, statement, period and currency across available years.
        for metric_facts in by_metric.values():
            ordered = sorted(
                metric_facts,
                key=lambda item: (int(item["fiscal_year"]), str(item.get("report_date") or "")),
            )
            deduplicated = {}
            for fact in ordered:
                deduplicated[str(fact["fiscal_year"])] = fact
            ordered = list(deduplicated.values())

            for previous, current in zip(ordered, ordered[1:]):
                previous_value = _decimal(previous.get("value"))
                if previous_value in (None, Decimal("0")):
                    continue

                evidence.append(_make_evidence(
                    "percentage_change",
                    [previous, current],
                    parameters={
                        "base_fact_id": previous["fact_id"],
                        "current_fact_id": current["fact_id"],
                        "formula": "(current - previous) / abs(previous) * 100",
                    },
                    question_hint=(
                        f"Ask how {current['metric_label']} changed in percentage terms "
                        f"from {previous['period']} {previous['fiscal_year']} to "
                        f"{current['period']} {current['fiscal_year']}."
                    ),
                ))

        unique = {item["evidence_id"]: item for item in evidence}
        return list(unique.values())
