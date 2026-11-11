# Prompts Reference

LLM prompts used by the evidence-based dataset generator.

## question_generation.md

**Used by:** question_generator.py → QuestionGenerator  
**LLM tier:** low  
**Output schema:** QuestionGenerationSchema

The question-generation LLM receives Python-built evidence metadata, not financial
values. Every question must reference exactly one evidence_id. An evidence item may
reference multiple atomic facts and specifies the permitted operation.

Supported question-generation operations include:
- lookup: request one source metric value
- profitability: interpret income-statement net income as net profit, net loss, or break-even
- gross_profit: calculate revenue minus cost of revenue
- gross_profit_margin: calculate the gross profit margin
- percentage_change: compare the same metric across two periods
- cross_statement_comparison: compare operating cash flow and net income for one period

The LLM returns a question and its evidence_id. It does not calculate answers or assign
capability tags.

## validation_question.md

**Used by:** validator.py → DatasetValidator  
**LLM tier:** low  
**Output schema:** QuestionValidationSchema

The validation LLM receives the question, evidence metadata, original referenced facts,
and the answer computed by Python. It checks whether the question is answerable from
those facts and whether it matches the evidence operation, company, metric and period.

## Prompt design principles

| Principle | Rationale |
|---|---|
| Values hidden from generation LLM | Prevents answers from leaking into question wording and avoids asking the LLM to calculate |
| Values shown to validation LLM | Lets the validator assess whether the question matches the actual source facts |
| Python owns evidence and formulas | Ensures compatible fact selection and deterministic expected answers |
| Structured Pydantic output | Keeps model responses machine-parseable |
| Separate generation and validation prompts | Gives each LLM call a narrow responsibility |
