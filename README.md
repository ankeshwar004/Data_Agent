# Financial Data Agent

A command-line financial data agent that retrieves company financial data from
Financial Modeling Prep (FMP), stores it in PostgreSQL, and answers natural
language questions using a LangGraph workflow.

The application:

1. Extracts the ticker, datasets, and requested years from a question.
2. Checks whether the requested data is already in PostgreSQL.
3. Fetches missing data from FMP and upserts it into the database.
4. Generates and executes a read-only SQL query.
5. Returns a natural language answer.

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
│   ├── coverage.py         # Checks available financial data
│   ├── etl_service.py      # Fetches and loads missing FMP data
│   ├── financial_repository.py
│   ├── schema.sql
│   └── seed.py
├── Models/schema.py         # Pydantic graph state models
├── utils/
│   ├── llm_picker.py        # OpenRouter model selection
│   └── prompts.py
├── fmp_client.py            # FMP API client
├── config.py                # Environment and application settings
└── main.py                  # CLI entry point
```

## Validation

Compile the main application modules:

```bash
venv/bin/python -m py_compile \
  main.py \
  fmp_client.py \
  database/coverage.py \
  database/etl_service.py \
  agents/data_agent.py
```

The FMP client and ETL flow can be tested with a fake HTTP session so no real
API request or database write is made. Keep API keys and database credentials
out of test output and source control.

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
