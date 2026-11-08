import json

from config import question_generation_prompt
from evals.base_model import QuestionGenerationSchema
from utils.llm_picker import get_llm


class QuestionGenerator:

    def __init__(self):

        self.llm = get_llm("low").with_structured_output(QuestionGenerationSchema)
        self.prompt = question_generation_prompt.read_text(encoding="utf-8")

    def generate(self, facts:list[dict]) -> list[dict]:
        """
        Generate questions based on the provided facts.
        """

        # Don't expose financial values to this LLM.
        context = [
            {
                "fact_id": f["fact_id"],
                "company": f["company"],
                "ticker": f["ticker"],
                "metric": f["metric_label"],
                "year": f["fiscal_year"],
                "period": f["period"],
                "currency": f["currency"]
            }
            for f in facts
        ]

        response = self.llm.invoke(
            self.prompt
            + "\n\nFACTS:\n"
            + json.dumps(context, indent=2)
        )

        return [question.model_dump() for question in response.questions]