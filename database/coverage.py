
from database.connection import db_connection


# Only allow known table names. Never take table names directly from user input.
DATASET_TABLES = {
    "income_statement": "income_statements",
    "balance_sheet": "balance_sheets",
    "cash_flow_statement": "cash_flow_statements",
}

def check_company_coverage(ticker: str) -> bool:
    """
    Check whether PostgreSQL contains a company profile for the given ticker.
    
    Args:
        ticker: Company ticker, e.g. "AAPL".
    
    Returns:
        True if the company profile exists, False otherwise.
    """
    
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty")
    
    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM companies
                WHERE ticker = %s
                """,
                (ticker,)
            )
            company = cur.fetchone()

    return company is not None



def check_company_financial_coverage(ticker: str,dataset: str,required_years: list[int]) -> dict:
    """
    Check whether PostgreSQL contains all requested annual financial statement records for a company.

    Args:
        ticker: Company ticker, e.g. "AAPL".
        dataset: income_statement, balance_sheet, or cash_flow_statement.
        required_years: Years needed, e.g. [2022, 2023, 2024, 2025].

    Returns:
        A dictionary describing available and missing years.
    """

    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty")

    if dataset not in DATASET_TABLES:
        raise ValueError(f"Unsupported dataset: {dataset}")
    
    if required_years is None:
        raise ValueError("required_years cannot be None")

    required_years = sorted(set(required_years))
    table_name = DATASET_TABLES[dataset]

    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT company_id
                FROM companies
                WHERE ticker = %s
                """,
                (ticker,),
            )

            company = cur.fetchone()

            if company is None:
                return {
                    "ticker": ticker,
                    "dataset": dataset,
                    "required_years": required_years,
                    "available_years": [],
                    "missing_years": required_years,
                    "complete": False,
                    "reason": "Company profile is missing",
                }

            company_id = company["company_id"]

            # Find which requested annual years exist.
            if required_years:
                cur.execute(
                    f"""
                    SELECT DISTINCT fiscal_year
                    FROM {table_name}
                    WHERE company_id = %s
                      AND period = 'FY'
                      AND fiscal_year = ANY(%s)
                    """,
                    (company_id, required_years),
                )

                rows = cur.fetchall()
                available_years = sorted(
                    row["fiscal_year"] for row in rows
                    if row["fiscal_year"] is not None
                )
            else:
                available_years = []

    # Calculate missing years.
    missing_years = sorted(
        set(required_years) - set(available_years)
    )

    return {
        "ticker": ticker,
        "dataset": dataset,
        "required_years": required_years,
        "available_years": available_years,
        "missing_years": missing_years,
        "complete": len(missing_years) == 0,
        "reason": (
            "All requested years are present"
            if not missing_years
            else "Some requested years are missing"
        ),
    }


def check_requested_coverage(ticker: str, datasets: list[str], required_years: list[int]) -> dict:
    """Check whether all requested financial datasets cover all required years."""

    if not  datasets:
        raise ValueError("At least one dataset must be requested.")

    datasets = list(dict.fromkeys(datasets))

    unsupported = [dataset for dataset in datasets if dataset not in DATASET_TABLES]
    
    if unsupported:
        raise ValueError(f"Unsupported datasets: {unsupported}")

    
    results = {
        dataset: check_company_financial_coverage(ticker=ticker, dataset=dataset, required_years=required_years)
        for dataset in datasets
    }

    all_complete = all(result["complete"] for result in results.values())

    return {
        "ticker": ticker,
        "required_years": required_years,
        "datasets": results,
        "complete": all_complete,
        "missing_data": {
            dataset: result["missing_years"]
            for dataset, result in results.items() if not result["complete"]
        },
    }