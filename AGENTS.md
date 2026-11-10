# Agent Documentation

## Overview

Financial Data Agent — a command-line tool that answers natural-language
financial questions. It fetches company data from Financial Modeling Prep
(FMP), stores it in PostgreSQL, and generates answers via a LangGraph
multi-agent workflow (Data Agent → ETL Agent → SQL Agent).

## Project Layout

```
agents/           LangGraph workflows (data_agent, etl_agent, sql_agent)
database/         PostgreSQL persistence: connection pool, schema, mapper,
                  coverage checks, ETL service, financial repository
Models/           Pydantic state schemas shared across agents
utils/            LLM picker, prompt templates, ETL tools
evals/            Synthetic evaluation-dataset generator pipeline
eval/             Fixed-case evaluation harness (offline + live)
tests/            Unit tests
fmp_client.py     FMP API client (HTTP, validation, auth)
config.py         Environment loading (.env) and application settings
main.py           CLI entry point
```

## Key Workflows

1. **Question → Answer** (`main.py` → `agents/data_agent.py`)
   - Extract ticker, datasets, years from the question.
   - Check PostgreSQL coverage; fetch missing data via ETL.
   - Generate and safety-check a SQL query; execute read-only.
   - Verify the result and return a natural-language answer.

2. **ETL** (`database/etl_service.py`)
   - Fetch from FMP, map camelCase → snake_case (`database/mapper.py`),
     upsert into PostgreSQL (`database/financial_repository.py`).

3. **Evaluation Dataset Generation** (`evals/dataset_generator/pipeline.py`)
   - Fetch real data → extract atomic facts → LLM generates questions →
     LLM validates → assemble ground-truth cases.

## Environment

Required variables (in `.env` at project root):

| Variable | Purpose |
|----------|---------|
| `FMP_API_KEY` | Financial Modeling Prep API key |
| `OPENROUTER_API_KEY` | LLM access via OpenRouter |
| `DATABASE_URL` | PostgreSQL connection string |

## Running

```bash
# Answer a question
venv/bin/python main.py "What was Apple's revenue in 2024?"

# Run tests
venv/bin/python -m pytest tests/

# Run offline evaluation
python -m eval.run_eval

# Generate synthetic evaluation dataset
python -m evals.dataset_generator.pipeline
```

## References

- [next_step.txt](file:///workspaces/Data_Agent/next_step.txt) — current evaluation priorities
- [README.md](file:///workspaces/Data_Agent/README.md) — full setup and usage guide
- [evals/dataset_generator/README.md](file:///workspaces/Data_Agent/evals/dataset_generator/README.md) — dataset generator docs
