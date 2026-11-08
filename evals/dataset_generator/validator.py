import json
import re

from config import validation_question_prompt
from evals.base_model import QuestionValidationSchema
from utils.llm_picker import get_llm

from evals.dataset_generator.answer_builder import build_case

def normalize_question(question):
    return re.sub(r"\s+"," ",question.lower().strip())


class DatasetValidator:

    def __init__(self):

        self.llm = get_llm("low").with_structured_output(QuestionValidationSchema)

        self.prompt = validation_question_prompt.read_text(encoding="utf-8")

    def validate(self, questions: list[dict], facts: list[dict]) -> tuple[list[dict], list[dict]]:

        fact_lookup = {fact["fact_id"]: fact for fact in facts}

        accepted = []
        rejected = []
        seen = set()

        for question_data in questions:

            try:
                fact_ids = question_data["fact_ids"]

                if not isinstance(fact_ids, list):
                    raise ValueError("Invalid fact IDs")

                if len(fact_ids) != 1:
                    raise ValueError("Only single-fact questions supported")

                if not question_data["question"].strip():
                    raise ValueError("Empty question")

                if any(fid not in fact_lookup for fid in fact_ids):
                    raise ValueError("Unknown fact ID")

                normalized = normalize_question(question_data["question"])

                if normalized in seen:
                    raise ValueError("Duplicate question")

                case = build_case(question_data, fact_lookup)

                referenced_facts = [ fact_lookup[fid] for fid in fact_ids]

                validation_input = {
                    "question": case["question"],
                    "facts": referenced_facts
                }

                response = self.llm.invoke(self.prompt+ "\n\nINPUT:\n"+ json.dumps( validation_input, indent=2, default=str))

                if not response.valid:
                    raise ValueError(response.reason or "LLM rejected")

                # Rebuild expected answer using Python.
                case = build_case(question_data, fact_lookup)

                # Verify expected value against source fact.
                original = fact_lookup[fact_ids[0]]

                assert case["value"] == original["value"]

                accepted.append(case)
                seen.add(normalized)

            except Exception as exc:

                rejected.append({
                    "question": question_data,
                    "reason": str(exc)
                })

        return accepted, rejected