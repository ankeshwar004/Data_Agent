# Dataset Generator

Synthetic evaluation-dataset pipeline for the financial-data AI agent. It fetches real
financial data from FMP, extracts atomic facts, constructs answerable evidence in Python,
asks an LLM to generate multiple natural-language questions, calculates ground truth in
Python, and validates each question.

## Architecture

~~~mermaid
flowchart TD
    A["FMP API"] --> B["fetcher.py"]
    B --> C["fact_extractor.py"]
    C --> D["Atomic facts"]
    D --> E["evidence_builder.py"]
    E --> F["Evidence items"]
    F --> G["question_generator.py"]
    G --> H["Generated questions"]
    H --> I["answer_builder.py"]
    I --> J["Python ground truth"]
    J --> K["validator.py"]
    K --> L["evaluation_dataset.json"]
    K --> M["rejected.json"]
~~~

## Design principles

- **Atomic facts are the source of truth.** Each fact points to one numeric field from
  one mapped FMP statement record.
- **Evidence is the question-generation unit.** Python decides which facts are compatible
  and which deterministic operation may be applied to them.
- **The LLM writes questions, not answers.** The question-generation LLM receives IDs,
  metric names, periods, allowed operations and hints, but not financial values.
- **Python calculates expected answers.** The answer builder uses original fact values
  and a small, explicit operation registry. It never executes arbitrary LLM-supplied code.
- **Tags are derived metadata.** capability_tags are assigned by Python from the evidence
  operation; the LLM does not need to classify its own questions.

## Supported evidence operations

| Operation | Facts used | Ground-truth calculation |
|---|---|---|
| lookup | One atomic fact | Return the source value |
| profitability | Net income | Positive = net profit; negative = net loss; zero = break-even |
| gross_profit | Revenue + cost of revenue | Revenue − cost of revenue |
| gross_profit_margin | Revenue + cost of revenue | (Revenue − cost of revenue) / Revenue × 100 |
| percentage_change | Same metric in two fiscal years | (Current − previous) / abs(previous) × 100 |
| cross_statement_comparison | Operating cash flow + net income for the same period | Boolean comparison |

This is an intentionally explicit first set of operations. Add new operations in
evidence_builder.py and answer_builder.py together, with deterministic tests, rather
than allowing the LLM to invent formulas.

## Directory structure

~~~text
evals/dataset_generator/
├── pipeline.py
├── fetcher.py
├── fact_extractor.py
├── evidence_builder.py
├── question_generator.py
├── answer_builder.py
├── validator.py
└── prompts/
    ├── question_generation.md
    └── validation_question.md
~~~

## Pipeline stages

1. **Fetch:** DatasetFetcher fetches company profile and mapped financial statements.
2. **Extract:** extract_company_facts converts numeric mapped fields into atomic facts
   with deterministic fact_id values.
3. **Build evidence:** build_evidence creates single-fact lookup evidence,
   supported financial calculations, same-metric year comparisons, and cross-statement
   comparisons. It checks that the required facts exist in the same company/period and
   currency context.
4. **Generate questions:** QuestionGenerator.generate groups evidence by ticker, sends
   bounded batches to the LLM, and asks for approximately QUESTIONS_PER_BATCH questions
   per batch. Each generated question must reference exactly one evidence_id. That
   evidence item can itself reference multiple atomic facts.
5. **Calculate and validate:** build_case computes the expected answer from source facts.
   DatasetValidator checks IDs and duplicates, then asks a second LLM pass whether the
   question is supported by the evidence and allowed operation.
6. **Save:** facts, evidence, accepted cases and rejected questions are written under
   OUTPUT_DIR.

## Evidence schema

An evidence item contains an evidence_id, operation, fact_ids, parameters, company and
period metadata, metric names, and a question_hint. For example, a gross-profit-margin
evidence item references revenue and cost_of_revenue and permits the formula
(revenue - cost_of_revenue) / revenue * 100.

The LLM returns only the question and its evidence reference. Python adds
capability_tags, source provenance, fact references, and the calculated answer to the
final case. Tags currently include retrieval, calculation, multi_fact, ratio, comparison,
multi_period, and cross_statement, as appropriate.

## Outputs

| File | Description |
|---|---|
| facts.json | Extracted atomic facts |
| evidence.json | Python-constructed evidence items |
| evaluation_dataset.json | Accepted evaluation cases and run statistics |
| rejected.json | Questions rejected by structural, calculation, or LLM validation |

The final case preserves the existing top-level question, ticker, year, metric, value,
dataset, period, and currency fields for compatibility. It also includes capability_tags
and an expected object with the operation, evidence ID, source facts, and answer details.

## Configuration and execution

The generator uses the existing settings in root config.py, including NUM_COMPANIES,
STATEMENT_LIMIT, QUESTIONS_PER_BATCH, OUTPUT_DIR, question_generation_prompt, and
validation_question_prompt.

Set FMP_API_KEY and the configured LLM provider credentials, then run from the
repository root:

~~~bash
python -m evals.dataset_generator.pipeline
~~~

## Important limitations

- The initial derived operations are deliberately limited to formulas implemented in
  Python. They do not attempt to support every possible financial calculation.
- Percentage change is skipped when the earlier value is zero.
- Evidence is only created when all required source facts exist with compatible company,
  period, and currency metadata.
- The LLM can produce several questions from one batch, but each question must point to
  one evidence item. The evidence item may reference one or multiple facts.
- Review generated/rejected samples and add unit tests for each new financial operation
  before expanding the operation registry.
