"""Database persistence layer for financial data fetched from FMP."""

from psycopg import sql
from psycopg.types.json import Json

from database.connection import db_connection


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


# ── Generic upsert builder ───────────────────────────────────────────────

def build_upsert_query(
    table: str,
    columns: list[str],
    conflict_columns: list[str],
    exclude_from_update: set[str] | None = None,
    extra_set_clauses: list[sql.Composable] | None = None,
    returning: str | None = None,
) -> sql.Composed:
    """
    Dynamically build an ``INSERT … ON CONFLICT … DO UPDATE`` query.

    Args:
        table:                Target table name.
        columns:              All columns to insert.
        conflict_columns:     Columns forming the conflict target for
                              ``ON CONFLICT (col, …)``.
        exclude_from_update:  Column names to skip in the DO UPDATE SET clause
                              (typically the conflict key columns).
        extra_set_clauses:    Additional ``sql.Composable`` expressions appended
                              to SET, e.g. ``updated_at = NOW()``.
        returning:            Column name to RETURNING (optional).

    Returns:
        A ``sql.Composed`` query ready for ``cursor.execute(query, params)``.
    """

    if not conflict_columns:
        raise ValueError("conflict_columns must be provided and non-empty")

    exclude = exclude_from_update or set()
    update_cols = [c for c in columns if c not in exclude]

    # INSERT INTO <table> (<col1>, <col2>, …)
    insert_clause = sql.SQL(", ").join(sql.Identifier(c) for c in columns)

    # VALUES (%(col1)s, %(col2)s, …)
    values_clause = sql.SQL(", ").join(sql.Placeholder(c) for c in columns)

    # ON CONFLICT (col1, col2, …)
    conflict_clause = sql.SQL("ON CONFLICT ({})").format(
        sql.SQL(", ").join(sql.Identifier(c) for c in conflict_columns)
    )

    # DO UPDATE SET <col> = EXCLUDED.<col>, …
    set_parts = [
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
        for c in update_cols
    ]
    if extra_set_clauses:
        set_parts.extend(extra_set_clauses)

    set_clause = sql.SQL(", ").join(set_parts)

    query = sql.SQL(
        "INSERT INTO {table} ({columns}) VALUES ({values}) "
        "{conflict} DO UPDATE SET {updates}"
    ).format(
        table=sql.Identifier(table),
        columns=insert_clause,
        values=values_clause,
        conflict=conflict_clause,
        updates=set_clause,
    )

    if returning:
        query = query + sql.SQL(" RETURNING {}").format(sql.Identifier(returning))

    return query


def prepare_params(mapped: dict, **extras) -> dict:
    """Merge mapped data with extras and wrap ``raw_payload`` for JSONB."""
    params = {**extras, **mapped}
    if "raw_payload" in params:
        params["raw_payload"] = Json(params["raw_payload"])
    return params


# ── Public upsert functions ──────────────────────────────────────────────

def upsert_company(mapped: dict) -> int:
    query = build_upsert_query(
        table="companies",
        columns=COMPANY_COLUMNS,
        conflict_columns=["ticker"],
        exclude_from_update={"ticker"},
        extra_set_clauses=[sql.SQL("updated_at = NOW()")],
        returning="company_id",
    )
    params = prepare_params(mapped)

    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            company_id = cur.fetchone()["company_id"]
            conn.commit()
    return company_id


def upsert_income_statement(company_id: int, mapped: dict) -> None:
    query = build_upsert_query(
        table="income_statements",
        columns=INCOME_STATEMENT_COLUMNS,
        conflict_columns=["company_id", "report_date", "period"],
        exclude_from_update={"company_id", "report_date", "period"},
    )
    params = prepare_params(mapped, company_id=company_id)

    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()


def upsert_balance_sheet(company_id: int, mapped: dict) -> None:
    query = build_upsert_query(
        table="balance_sheets",
        columns=BALANCE_SHEET_COLUMNS,
        conflict_columns=["company_id", "report_date", "period"],
        exclude_from_update={"company_id", "report_date", "period"},
    )
    params = prepare_params(mapped, company_id=company_id)

    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()


def upsert_cash_flow_statement(company_id: int, mapped: dict) -> None:
    query = build_upsert_query(
        table="cash_flow_statements",
        columns=CASH_FLOW_COLUMNS,
        conflict_columns=["company_id", "report_date", "period"],
        exclude_from_update={"company_id", "report_date", "period"},
    )
    params = prepare_params(mapped, company_id=company_id)

    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()