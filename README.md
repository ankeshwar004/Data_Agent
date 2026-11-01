# Financial Data Agent

A command-line financial data agent that retrieves company financial data from
Financial Modeling Prep (FMP), stores it in PostgreSQL, and answers natural
language questions using a LangGraph workflow.

The application:

1. Extracts the ticker, datasets, and requested years from a question.
2. Checks whether the requested data is already in PostgreSQL.
3. Fetches missing data from FMP and upserts it into the database.
4. Generates a SQL query and checks it with a safety judge.
5. Executes the approved query in a read-only transaction.
6. Verifies the result and returns a natural language answer.

The workflow retries failed ETL and SQL steps within bounded retry budgets. The
ETL layer only loads annual `FY` records for the requested fiscal years.

## Requirements

- Python 3.12 or 3.13 recommended.
- PostgreSQL 14 or newer.
- An FMP API key.
- An OpenRouter API key.

Python 3.14 may display a Pydantic compatibility warning from the LangChain
dependency tree. The application can still run, but Python 3.12 or 3.13 is
recommended for the best dependency compatibility.

## Setup

From the repository root:

```bash
cd /workspaces/Data_Agent
```

Create and activate a virtual environment:

```bash
python3.12 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

If the virtual environment already exists, use:

```bash
venv/bin/python -m pip install -r requirements.txt
```

## Environment variables

Create a `.env` file in the repository root. Do not commit this file.

```env
FMP_API_KEY=your_fmp_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# Use either DATABASE_URL or the individual PostgreSQL settings.
DATABASE_URL=postgresql://db-user:db-password@db.example.com:5432/database
```

The application loads `.env` through [`config.py`](config.py).

Alternatively, configure PostgreSQL with individual variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=postgres
```

The current low-level agent uses OpenRouter, so `OPENROUTER_API_KEY` is
required. `OPENAI_API_KEY` is not required by the current configuration.
Set `OPENROUTER_MODEL` to override the default model
(`nvidia/nemotron-3-ultra-550b-a55b:free`).

Verify that the application can load the credentials without printing them:

```bash
venv/bin/python -c "import config; print('FMP configured:', bool(config.os.getenv('FMP_API_KEY'))); print('OpenRouter configured:', bool(config.OPENROUTER_API_KEY)); print('Database configured:', bool(config.DATABASE_URL))"
```

## Initialize the database

Make sure PostgreSQL is running and `DATABASE_URL` is correct, then run:

```bash
venv/bin/python database/seed.py
```

This creates and verifies the following tables:

- `companies`
- `income_statements`
- `balance_sheets`
- `cash_flow_statements`

The schema is defined in [`database/schema.sql`](database/schema.sql).

## Run the agent

Ask a question as a command-line argument:

```bash
venv/bin/python main.py "What was Apple's revenue in 2024?"
```

Example output:

```text
Apple's total revenue for fiscal year 2024 was $391.035 billion.
```

If no argument is supplied, the application reads one question from standard
input:

```bash
venv/bin/python main.py
```

Then enter a question such as:

```text
Show Microsoft's income statement for 2023 and 2024.
```

## Supported data

The agent currently supports:

- Company profiles
- Income statements
- Balance sheets
- Cash flow statements

Financial data is filtered to annual `FY` records. FMP may return
`fiscalYear` as a string, so the ETL layer normalizes it before matching
requested years.

## Project structure

```text
.
├── agents/
│   ├── data_agent.py       # Main orchestration graph
│   ├── etl_agent.py        # Tool-based ETL graph
│   └── sql_agent.py        # Safe SQL and answer generation graph
├── database/
│   ├── connection.py       # PostgreSQL connection pool lifecycle
│   ├── coverage.py         # Checks available financial data
│   ├── database.py         # Schema inspection and SQL execution
│   ├── etl_service.py      # Fetches and loads missing FMP data
│   ├── financial_repository.py
│   ├── loader.py           # Database loading helpers
│   ├── mapper.py           # FMP-to-database mappings
│   ├── queries.py           # Database queries
│   ├── schema.sql
│   └── seed.py
├── Models/schema.py         # Pydantic graph state models
├── utils/
│   ├── etl_tools.py         # Generic extraction and load tools
│   ├── llm_picker.py        # OpenRouter model selection
│   └── prompts.py           # Agent prompts
├── fmp_client.py            # FMP API client
├── config.py                # Environment and application settings
├── main.py                  # CLI entry point
├── graph_png/               # Generated workflow diagrams
├── eval/
│   ├── cases.json           # Fixed evaluation questions and expected values
│   ├── cases.py             # Dataset loading and report scoring
│   ├── offline.py           # Deterministic fixture evaluation
│   ├── live.py              # PostgreSQL/FMP/LLM evaluation
│   └── run_eval.py          # CLI entry point
└── tests/                   # Unit tests for agents and database services
```

## Architecture

The application is composed of three LangGraph workflows:

- **Data agent**: extracts request details, checks database coverage, routes
  missing data through ETL, and coordinates SQL retries and result
  verification.
- **ETL agent**: provides tool-based extraction and financial-data loading.
- **SQL agent**: curates the question, generates SQL from the database schema,
  checks query safety, executes approved read-only queries, and formats the
  answer.

Workflow diagrams are available in [`graph_png/`](graph_png/):

- [`data_agent_graph.png`](graph_png/data_agent_graph.png)
- [`etl_agent_graph.png`](graph_png/etl_agent_graph.png)
- [`sql_agent_graph.png`](graph_png/sql_agent_graph.png)

## Test and validate

Run the unit tests:

```bash
venv/bin/python -m pytest tests/
```

Compile the application modules:

```bash
venv/bin/python -m py_compile \
  main.py \
  fmp_client.py \
  database/coverage.py \
  database/etl_service.py \
  agents/data_agent.py
```

The tests use fakes and mocks for external services where appropriate. Tests
that exercise PostgreSQL require a configured database. Keep API keys and
database credentials out of test output and source control.

### Run the deterministic end-to-end evaluation

The evaluation harness uses fixed fixtures and an in-memory
PostgreSQL-shaped store. It does not require PostgreSQL, FMP credentials, or
an LLM:

```bash
python -m eval.run_eval
python -m eval.run_eval --json
```

The 45 cases cover 15 data-present cases, 15 missing-data cases, and 15
injected-failure cases. The 15 records in
[`eval/cases.json`](eval/cases.json) are repeated across three deterministic
runs so the fixture set remains reviewable. A financial task passes only when
the expected value is returned from an executed query; missing-data cases also
require the record to be loaded. Failure cases pass only when bounded retries
terminate with an explicit error and no value is invented.

The report separates task completion success rate from failure handling rate
and reports the autonomous workflow's change in percentage points against the
simpler one-attempt baseline.

Offline reports also include SQL first-attempt and final execution success
rates, plus ETL complete-request success and correctly loaded-record counts.
SQL execution denominators include only cases that reached SQL generation;
FMP/ETL failures that terminate before SQL are not misclassified as SQL
failures.

### Run against live services

Use a dedicated PostgreSQL database for evaluation. The live mode never
defaults to the application's normal `DATABASE_URL` and refuses to start
unless all three service credentials are present:

```env
EVAL_DATABASE_URL=postgresql://user:password@localhost:5432/data_agent_eval
FMP_API_KEY=your_fmp_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=your_model
```

Then run:

```bash
python -m eval.run_eval --live --json
```

Live evaluation runs the 15 unique fixture questions through the production
graph and verifies the requested
fiscal record with an independent read-only SQL query. It checks initial and
post-run coverage, the agent's executed query result, final completion, and
the expected value. Failure cases are reported as skipped because simulating
timeouts or database faults against live services would require a fault
injection proxy; they are not silently counted as passed.

The live report includes `sql_execution.first_attempt_success_rate`,
`sql_execution.final_execution_success_rate`,
`etl_coverage.complete_request_success_rate`, and
`etl_coverage.records_loaded_correctly`. These metrics are based on the
production graph's per-attempt state, not inferred from the final answer.

## Troubleshooting

### `FMP_API_KEY is not configured`

Run the application through `config.py` rather than checking with plain
`os.getenv`, because plain Python does not automatically load `.env`:


### `No valid financial records found for the requested years`

The FMP response may not contain an annual `FY` record for the requested year,
or the API key may not have access to the requested endpoint. Confirm the
ticker, year, FMP plan limits, and API response.

### `ETL retry budget exhausted`

The final error now includes the last ETL result. Resolve that underlying
error, then rerun the command. Common causes include invalid credentials,
database connectivity, API rate limits, and missing FMP records.

### Pydantic v1 warning on Python 3.14

Some LangChain dependencies import Pydantic v1 compatibility support. Use
Python 3.12 or 3.13 to avoid the warning. Suppressing the warning is possible,
but upgrading or changing the Python version is preferable to hiding it.

## Security

- Never commit `.env` or API keys.
- Rotate credentials if they have been exposed.
- The SQL agent executes queries in a read-only transaction.
- Do not paste live credentials into issue reports, logs, or terminal output.
