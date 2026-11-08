from database.financial_repository import (
    upsert_company,
    upsert_income_statement,
    upsert_balance_sheet,
    upsert_cash_flow_statement,
)

from database.mapper import (
    map_company_profile,
    map_income_statement,
    map_balance_sheet,
    map_cash_flow_statement,
)

DATASET_TABLES = {
    "income_statement": "income_statements",
    "balance_sheet": "balance_sheets",
    "cash_flow_statement": "cash_flow_statements",
}

DATASETS_CONFIG = {
    "income_statement": {
        "endpoint": "income-statement",
        "mapper": map_income_statement,
        "upsert": upsert_income_statement,
    },
    "balance_sheet": {
        "endpoint": "balance-sheet-statement",
        "mapper": map_balance_sheet,
        "upsert": upsert_balance_sheet,
    },
    "cash_flow_statement": {
        "endpoint": "cash-flow-statement",
        "mapper": map_cash_flow_statement,
        "upsert": upsert_cash_flow_statement,
    },
}

COMPANY_COLUMNS = [
    "ticker", "company_name", "cik", "isin", "cusip",
    "exchange", "exchange_full_name", "currency",
    "sector", "industry", "website", "description", "ceo", "country",
    "market_cap", "current_price", "beta", "last_dividend",
    "ipo_date", "is_actively_trading",
    "raw_payload",
]

INCOME_STATEMENT_COLUMNS = [
    "company_id",
    "report_date", "fiscal_year", "period", "reported_currency",
    "filing_date", "accepted_date",
    "revenue", "cost_of_revenue", "gross_profit",
    "operating_expenses", "operating_income",
    "ebit", "ebitda",
    "income_before_tax", "income_tax_expense", "net_income",
    "eps", "eps_diluted",
    "raw_payload",
]

BALANCE_SHEET_COLUMNS = [
    "company_id",
    "report_date", "fiscal_year", "period", "reported_currency",
    "filing_date", "accepted_date",
    "cash_and_cash_equivalents",
    "total_current_assets", "total_assets",
    "total_current_liabilities", "total_liabilities",
    "total_stockholders_equity", "total_equity",
    "total_debt", "net_debt",
    "raw_payload",
]

CASH_FLOW_COLUMNS = [
    "company_id",
    "report_date", "fiscal_year", "period", "reported_currency",
    "filing_date", "accepted_date",
    "net_income",
    "operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
    "capital_expenditure", "free_cash_flow",
    "net_change_in_cash",
    "raw_payload",
]
