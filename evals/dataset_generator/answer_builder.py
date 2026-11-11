from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation


def _number(value) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Non-numeric source value: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Non-finite source value: {value!r}")
    return number


def _as_json_number(value: Decimal):
    # Keep integers as integers and calculated values as floats for JSON output.
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _derive_tags(operation: str, fact_count: int) -> list[str]:
    tags = {
        "lookup": ["retrieval"],
        "gross_profit": ["calculation", "multi_fact"],
        "gross_profit_margin": ["calculation", "ratio", "multi_fact"],
        "percentage_change": ["calculation", "comparison", "multi_period"],
        "cross_statement_comparison": ["comparison", "cross_statement", "multi_fact"],
    }
    result = list(tags.get(operation, []))
    if fact_count > 1 and "multi_fact" not in result:
        result.append("multi_fact")
    return result


def _calculate(evidence: dict, fact_lookup: dict) -> dict:
    operation = evidence["operation"]
    facts = [fact_lookup[fact_id] for fact_id in evidence["fact_ids"]]
    params = evidence.get("parameters", {})

    if operation == "lookup":
        result = _number(facts[0]["value"])
        return {"value": _as_json_number(result), "unit": facts[0].get("currency")}

    if operation in {"gross_profit", "gross_profit_margin"}:
        revenue = _number(fact_lookup[params["revenue_fact_id"]]["value"])
        cost = _number(fact_lookup[params["cost_fact_id"]]["value"])
        gross_profit = revenue - cost

        if operation == "gross_profit":
            return {"value": _as_json_number(gross_profit), "unit": evidence.get("currency")}

        if revenue == 0:
            raise ValueError("Cannot calculate gross profit margin with zero revenue")
        margin = gross_profit / revenue * Decimal("100")
        return {"value": round(float(margin), 4), "unit": "%"}

    if operation == "percentage_change":
        base = _number(fact_lookup[params["base_fact_id"]]["value"])
        current = _number(fact_lookup[params["current_fact_id"]]["value"])
        if base == 0:
            raise ValueError("Cannot calculate percentage change from a zero base")
        change = (current - base) / abs(base) * Decimal("100")
        return {"value": round(float(change), 4), "unit": "%"}

    if operation == "cross_statement_comparison":
        left = _number(fact_lookup[params["left_fact_id"]]["value"])
        right = _number(fact_lookup[params["right_fact_id"]]["value"])
        comparator = params.get("comparator")
        if comparator == "greater_than":
            result = left > right
        elif comparator == "less_than":
            result = left < right
        elif comparator == "equal_to":
            result = left == right
        else:
            raise ValueError(f"Unsupported comparison operator: {comparator}")
        return {
            "value": result,
            "unit": "boolean",
            "details": {
                "left_metric": facts[0]["metric"],
                "right_metric": facts[1]["metric"],
                "left_value": _as_json_number(left),
                "right_value": _as_json_number(right),
                "comparator": comparator,
            },
        }

    raise ValueError(f"Unsupported evidence operation: {operation}")


def build_case(question_data: dict, evidence_lookup: dict, fact_lookup: dict) -> dict:
    """Build a deterministic evaluation case from one evidence item."""

    evidence_id = question_data["evidence_id"]
    evidence = evidence_lookup[evidence_id]
    fact_ids = evidence["fact_ids"]
    facts = [fact_lookup[fact_id] for fact_id in fact_ids]

    if not facts:
        raise ValueError("Evidence must reference at least one fact")

    question = question_data["question"].strip()
    if not question:
        raise ValueError("Question cannot be empty")

    answer = _calculate(evidence, fact_lookup)
    case_id = hashlib.sha256(question.lower().encode("utf-8")).hexdigest()[:12]

    years = sorted({fact["fiscal_year"] for fact in facts}, key=str)
    statements = sorted({fact["statement"] for fact in facts})
    metrics = [fact["metric"] for fact in facts]
    report_dates = sorted({str(fact["report_date"]) for fact in facts if fact.get("report_date")})

    # Preserve the legacy top-level fields used by the existing evaluator.
    single_fact = facts[0] if len(facts) == 1 else None
    return {
        "id": f"generated-{case_id}",
        "group": "generated",
        "question": question,
        "ticker": evidence["ticker"],
        "year": years[0] if len(years) == 1 else years,
        "metric": single_fact["metric"] if single_fact else evidence["operation"],
        "value": answer["value"],
        "dataset": statements[0] if len(statements) == 1 else "cross_statement",
        "period": evidence["period"],
        "currency": answer.get("unit"),
        "capability_tags": _derive_tags(evidence["operation"], len(facts)),
        "expected": {
            "evidence_id": evidence_id,
            "operation": evidence["operation"],
            "parameters": evidence.get("parameters", {}),
            "fact_ids": fact_ids,
            "facts": facts,
            "answer": answer,
        },
        "source": {
            "provider": "FMP",
            "endpoints": statements,
            "report_dates": report_dates,
        },
    }
