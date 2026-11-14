from __future__ import annotations

from pydantic import BaseModel, Field


class GeneratedQuestionSchema(BaseModel):
    question: str = Field(
        description="A natural-language question answerable from one supplied evidence item."
    )
    evidence_id: str = Field(
        description="The exact evidence_id that supports this question."
    )


class QuestionGenerationSchema(BaseModel):
    questions: list[GeneratedQuestionSchema] = Field(
        default_factory=list,
        description="Multiple diverse questions generated from the supplied evidence.",
    )


class QuestionValidationSchema(BaseModel):
    valid: bool = Field(
        description="Whether the question is fully supported by the referenced evidence."
    )
    reason: str = Field(
        description="Brief explanation for the validation decision."
    )