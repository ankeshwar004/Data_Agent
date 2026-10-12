import config

from datetime import date

from fmp_client import FMPClient
from database.connection import db_connection
from database.coverage import check_company_financial_coverage

from database.mapper import (
    map_company_profile,
    map_income_statement,
    map_balance_sheet,
    map_cash_flow_statement,
)

from database.financial_repository import (
    upsert_company,
    upsert_income_statement,
    upsert_balance_sheet,
    upsert_cash_flow_statement,
)

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


def ensure_company_profile(fmp_client: FMPClient, ticker: str) -> int:
    """Ensure company exists and return company_id."""
    
    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT company_id FROM companies WHERE ticker = %s", (ticker,))
            row = cur.fetchone()
            if row:
                return row["company_id"]
            
    # Fetch and upsert profile if missing
    profile_data = fmp_client.fetch("profile", ticker, limit=1)
    if not profile_data:
        raise ValueError(f"Company profile not found for ticker: {ticker}")
    
    mapped = map_company_profile(profile_data[0])
    return upsert_company(mapped)



def fetch_and_load_financial_data(ticker: str, dataset: str, required_years: list[int]) -> dict:
    """
    Fetch missing annual financial data from FMP and load it into PostgreSQL.

    Returns a structured result for the Data Agent controller.
    """

    ticker = ticker.strip().upper()
    required_years = sorted(set(required_years))

    result = {
        "success": False,
        "ticker": ticker,
        "dataset": dataset,
        "requested_years": required_years,
        "fetched_records": 0,
        "loaded_records": 0,
        "missing_years": required_years.copy(),
        "error": None,
    }

    try:
        if not ticker:
            raise ValueError("Ticker cannot be empty.")

        if dataset not in DATASETS_CONFIG:
            raise ValueError(f"Unsupported dataset: {dataset}")

        if not required_years:
            raise ValueError("At least one fiscal year is required.")

        if any(year < 2000 or year > date.today().year + 1 for year in required_years):
            raise ValueError("One or more requested years are invalid.")

        dataset_config = DATASETS_CONFIG[dataset]

        coverage = check_company_financial_coverage(ticker, dataset, required_years)

        if coverage["complete"]:
            result.update(success=True,missing_years=[])
            return result

        missing_years = coverage["missing_years"]

        client = FMPClient()

        # FMP's current client accepts a record limit, not a year filter.
        limit = max(config.RECORD_LIMIT, date.today().year - min(missing_years) + 1)
        records = client.fetch(dataset_config["endpoint"], ticker, limit=limit)

        result["fetched_records"] = len(records)

        if not records:
            raise ValueError("No financial records fetched from FMP.")
        
        unique_records = {record["fiscalYear"]: record for record in records if record.get("fiscalYear") in missing_years and record.get("period") == "FY"}
        
        if not unique_records:
            raise ValueError("No valid financial records found for the requested years.")
        
        records = list(unique_records.values())

        company_id = ensure_company_profile(client, ticker)

        for record in records:
            mapped = dataset_config["mapper"](record)
            dataset_config["upsert"](company_id, mapped)
            result["loaded_records"] += 1

        final_coverage = check_company_financial_coverage(ticker, dataset, required_years)

        result["missing_years"] = final_coverage["missing_years"]
        result["success"] = final_coverage["complete"]

        if not result["success"]:
            result["error"] = "ETL finished, but some requested years are still missing."

        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result