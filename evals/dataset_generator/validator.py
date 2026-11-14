import json
import re

from config import validation_question_prompt
from evals.base_model import QuestionValidationSchema
from utils.llm_picker import get_llm
from evals.dataset_generator.answer_builder import build_case


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.lower().strip())


class DatasetValidator:
    def __init__(self):
        self.llm = get_llm("low").with_structured_output(QuestionValidationSchema)
        self.prompt = validation_question_prompt.read_text(encoding="utf-8")

    def validate(
        self,
        questions: list[dict],
        evidence_items: list[dict],
        facts: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        fact_lookup = {fact["fact_id"]: fact for fact in facts}
        evidence_lookup = {item["evidence_id"]: item for item in evidence_items}

        accepted = []
        rejected = []
        seen = set()

        for question_data in questions:
            try:
                question = question_data.get("question", "")
                evidence_id = question_data.get("evidence_id")

                if not isinstance(question, str) or not question.strip():
                    raise ValueError("Empty question")
                if not evidence_id or evidence_id not in evidence_lookup:
                    raise ValueError("Unknown evidence ID")

                normalized = normalize_question(question)
                if normalized in seen:
                    raise ValueError("Duplicate question")

                evidence = evidence_lookup[evidence_id]
                fact_ids = evidence.get("fact_ids", [])
                if not fact_ids:
                    raise ValueError("Evidence contains no fact IDs")
                if any(fact_id not in fact_lookup for fact_id in fact_ids):
                    raise ValueError("Evidence references an unknown fact ID")

                # Build first so unsupported operations or invalid arithmetic are
                # rejected deterministically before spending an LLM validation call.
                case = build_case(question_data, evidence_lookup, fact_lookup)

                validation_input = {
                    "question": question,
                    "evidence": {
                        "evidence_id": evidence_id,
                        "operation": evidence["operation"],
                        "parameters": evidence.get("parameters", {}),
                        "company": evidence["company"],
                        "ticker": evidence["ticker"],
                        "fiscal_year": evidence["fiscal_year"],
                        "period": evidence["period"],
                        "statements": evidence["statements"],
                        "metrics": evidence["metrics"],
                        "question_hint": evidence["question_hint"],
                    },
                    "facts": case["expected"]["facts"],
                    "python_computed_answer": case["expected"]["answer"],
                }

                response = self.llm.invoke(
                    self.prompt
                    + "\n\nINPUT:\n"
                    + json.dumps(validation_input, indent=2, default=str)
                )
                if not response.valid:
                    raise ValueError(response.reason or "LLM rejected question")

                accepted.append(case)
                seen.add(normalized)

            except Exception as exc:
                rejected.append({
                    "question": question_data,
                    "reason": str(exc),
                })

        return accepted, rejected
