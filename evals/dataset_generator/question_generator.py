import json
from collections import defaultdict, deque

from config import QUESTIONS_PER_BATCH, question_generation_prompt
from evals.base_model import QuestionGenerationSchema
from utils.llm_picker import get_llm


class QuestionGenerator:
    """Generate multiple questions from Python-constructed evidence batches."""

    EVIDENCE_PER_BATCH = 30

    def __init__(self):
        self.llm = get_llm("low").with_structured_output(QuestionGenerationSchema)
        self.prompt = question_generation_prompt.read_text(encoding="utf-8")

    def _interleave_operations(self, items: list[dict]) -> list[dict]:
        # EvidenceBuilder emits many lookup items. Interleave operation buckets so
        # each LLM batch can contain retrieval, calculations and comparisons.
        buckets = defaultdict(deque)
        for item in items:
            buckets[item["operation"]].append(item)

        ordered = []
        operations = sorted(buckets)
        while any(buckets.values()):
            for operation in operations:
                if buckets[operation]:
                    ordered.append(buckets[operation].popleft())
        return ordered

    def generate(self, evidence_items: list[dict]) -> list[dict]:
        # Keep a company's evidence together; cross-statement evidence remains intact.
        by_ticker = defaultdict(list)
        for item in evidence_items:
            by_ticker[item["ticker"]].append(item)

        generated = []
        for ticker, ticker_evidence in by_ticker.items():
            balanced_evidence = self._interleave_operations(ticker_evidence)

            for start in range(0, len(balanced_evidence), self.EVIDENCE_PER_BATCH):
                batch = balanced_evidence[start:start + self.EVIDENCE_PER_BATCH]

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
