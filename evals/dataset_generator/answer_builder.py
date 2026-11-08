import hashlib

def build_case(question_data: dict, fact_lookup: dict) -> dict:
    """
    Build a case dictionary from the question data and fact lookup (i.e., a mapping of fact IDs to fact data).
    """

    fact_ids = question_data["fact_ids"]

    facts = [fact_lookup[fact_id] for fact_id in fact_ids]

    if len(facts) != 1:
        raise ValueError("Currenlty supports single-fact questions only")

    fact = facts[0]

    case_id = hashlib.sha256(question_data["question"].lower().encode()).hexdigest()[:12]

    return {
        "id": f"generated-{case_id}",

        "group": "generated",

        "question": question_data["question"],

        # Compatible with your existing evaluator fields.
        "ticker": fact["ticker"],
        "year": fact["fiscal_year"],
        "metric": fact["metric"],
        "value": fact["value"],

        "dataset": fact["statement"],
        "period": fact["period"],
        "currency": fact["currency"],

        "expected": {
            "fact_ids": fact_ids,
            "facts": facts
        },

        "source": {
            "provider": "FMP",
            "endpoint": fact["statement"],
            "report_date": fact["report_date"]
        }
    }