# Prompts Reference

LLM system prompts used by the dataset generator pipeline.

---

## `question_generation..md`

**Used by:** `question_generator.py` → `QuestionGenerator`  
**LLM tier:** low (cheap/fast)  
**Output schema:** `QuestionGenerationSchema` (Pydantic)

### Purpose
Instructs the LLM to generate natural-language benchmark questions from a list of financial fact **metadata** (no actual values are exposed).

### Rules enforced by the prompt
1. Only generate questions supported by the supplied facts.
2. Every question must reference one or more `fact_id`s.
3. Do not invent financial values.
4. Do not use outside financial knowledge.
5. Do not require unsupported calculations.
6. Use natural variations in wording.
7. Generate single-fact questions initially.
8. Avoid duplicate questions.
9. Ensure company and fiscal year are clear in every question.
10. Do not ask about data that is missing.

### Example LLM input
```json
[
  {
    "fact_id": "a1b2c3d4e5f6a7b8",
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "metric": "Net Income",
    "year": 2023,
    "period": "FY",
    "currency": "USD"
  }
]
```

### Example expected output
```json
{
  "questions": [
    {
      "question": "What was Apple's net income for fiscal year 2023?",
      "fact_ids": ["a1b2c3d4e5f6a7b8"],
      "question_type": "single_fact"
    }
  ]
}
```

> **Important:** Financial values are intentionally **omitted** from the LLM input.  
> The LLM writes the question; the actual numeric answer is sourced from the fact store — never from LLM output.

---

## `validation_question.md`

**Used by:** `validator.py` → `DatasetValidator`  
**LLM tier:** low (cheap/fast)  
**Output schema:** `QuestionValidationSchema` (Pydantic)

### Purpose
Instructs the LLM to judge whether a generated question is valid given the referenced facts.

### Checks the LLM performs
1. Is the question answerable using the provided facts?
2. Does it refer to the correct company?
3. Does it refer to the correct fiscal year?
4. Does it request the correct financial metric?
5. Does it require any unsupported calculation?
6. Is it ambiguous?
7. Are the referenced facts sufficient to answer it?

### Example LLM input
```json
{
  "question": "What was Apple's net income for fiscal year 2023?",
  "facts": [
    {
      "fact_id": "a1b2c3d4e5f6a7b8",
      "ticker": "AAPL",
      "company": "Apple Inc.",
      "statement": "income_statement",
      "metric": "net_income",
      "value": 96995000000,
      "fiscal_year": 2023,
      "period": "FY",
      "currency": "USD"
    }
  ]
}
```

### Expected output
```json
{
  "valid": true,
  "reason": "Question is unambiguous, references the correct metric and year, and is fully supported by the supplied fact."
}
```

---

## Prompt Design Principles

| Principle | Rationale |
|-----------|-----------|
| Values hidden from generation LLM | Prevents hallucinated numbers from leaking into the question text |
| Values shown to validation LLM | Required for the LLM to verify the question is factually grounded |
| Structured output (Pydantic) | Guarantees machine-parseable responses; avoids free-text parsing fragility |
| Low-tier LLM for both | These tasks are mostly rule-following, not complex reasoning — fast + cheap models suffice |
| Separate generation and validation prompts | Separation of concerns; each LLM call has a narrow, well-defined task |
