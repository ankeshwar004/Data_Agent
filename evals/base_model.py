from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal

class GeneratedQuestionSchema(BaseModel):
    question: str = Field(description="A natural-language question supported by the supplied facts.")
    fact_ids: list[str] = Field(description="Fact IDs needed to answer the question.")
    question_type: Literal["single_fact"] = Field(
        description="The type of question generated from the supplied facts."
    )


class QuestionGenerationSchema(BaseModel):
    questions: list[GeneratedQuestionSchema] = Field(
        default_factory=list,
        description="Questions generated from the supplied financial facts.",
    )


class QuestionValidationSchema(BaseModel):
    valid: bool = Field(
        description="Whether the question is fully supported by the referenced facts."
    )
    reason: str = Field(
        description="Brief explanation for the validation decision."
    )
