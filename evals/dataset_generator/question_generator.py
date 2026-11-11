import json
from collections import defaultdict

from config import QUESTIONS_PER_BATCH, question_generation_prompt
from evals.base_model import QuestionGenerationSchema
from utils.llm_picker import get_llm


class QuestionGenerator:
    """Generate multiple questions from Python-constructed evidence batches."""

    EVIDENCE_PER_BATCH = 30

    def __init__(self):
        self.llm = get_llm("low").with_structured_output(QuestionGenerationSchema)
        self.prompt = question_generation_prompt.read_text(encoding="utf-8")

    def generate(self, evidence_items: list[dict]) -> list[dict]:
        # Keep a company's evidence together where possible. Evidence may span
        # statements, so grouping by statement here would lose cross-statement cases.
        by_ticker = defaultdict(list)
        for item in evidence_items:
            by_ticker[item["ticker"]].append(item)

        generated = []
        for ticker, ticker_evidence in by_ticker.items():
            for start in range(0, len(ticker_evidence), self.EVIDENCE_PER_BATCH):
                batch = ticker_evidence[start:start + self.EVIDENCE_PER_BATCH]

                # Do not expose numeric financial values to the question LLM.
                context = [
                    {
                        "evidence_id": item["evidence_id"],
                        "operation": item["operation"],
                        "company": item["company"],
                        "ticker": item["ticker"],
                        "fiscal_year": item["fiscal_year"],
                        "period": item["period"],
                        "currency": item.get("currency"),
                        "statements": item["statements"],
                        "metrics": item["metrics"],
                        "metric_labels": item["metric_labels"],
                        "question_hint": item["question_hint"],
                    }
                    for item in batch
                ]

                response = self.llm.invoke(
                    self.prompt
                    + f"\n\nGenerate approximately {QUESTIONS_PER_BATCH} questions "
                      "from this batch. Prefer different evidence IDs and reasoning "
                      "patterns; do not generate trivial paraphrases of the same question."
                    + "\n\nEVIDENCE:\n"
                    + json.dumps(context, indent=2, default=str)
                )

                valid_ids = {item["evidence_id"] for item in batch}
                for question in response.questions:
                    if question.evidence_id not in valid_ids:
                        continue
                    generated.append(question.model_dump())

        return generated
