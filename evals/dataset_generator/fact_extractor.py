import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any


# These fields describe a financial record. They are not financial metrics themselves.
METADATA_FIELDS = {
    "report_date",
    "fiscal_year",
    "period",
    "reported_currency",
    "filing_date",
    "accepted_date",
    "raw_payload",
}


def make_fact_id(ticker: str, statement: str, fiscal_year: Any, period: str, metric: str, report_date: Any) -> str:
    """
    Generate a deterministic ID for a financial fact.
    """

    raw = (
        f"{ticker}:{statement}:{fiscal_year}:"
        f"{period}:{metric}:{report_date}"
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def is_numeric(value: Any) -> bool:
    """
    Check whether a value represents a valid number.
    Excludes booleans, None, NaN and infinity.
    """

    if value is None or isinstance(value, bool):
        return False

    try:
        number = Decimal(str(value))

        return number.is_finite()

    except (InvalidOperation, ValueError, TypeError):
        return False


def extract_facts_from_record(ticker: str, company: str, statement: str, mapped_record: dict) -> list[dict]:
    """
    Extract financial facts from an already mapped FMP record.
    The mapped record must come from database/mapper.py.

    All numeric fields except metadata are treated as financial metrics.
    """

    fiscal_year = mapped_record.get("fiscal_year")
    period = mapped_record.get("period")
    report_date = mapped_record.get("report_date")

    if fiscal_year is None:
        raise ValueError(f"Missing fiscal_year for {ticker}")
    if not period:
        raise ValueError(f"Missing period for {ticker}")

    facts = []
    for metric, value in mapped_record.items():
        if metric in METADATA_FIELDS or not is_numeric(value):
            continue

        fact_id = make_fact_id(
            ticker=ticker,
            statement=statement,
            fiscal_year=fiscal_year,
            period=period,
            metric=metric,
            report_date=report_date,
        )

        facts.append({
            "fact_id": fact_id,

            "ticker": ticker,
            "company": company,

            "statement": statement,
            "metric": metric,
            "metric_label": metric.replace("_", " ").title(),

            "value": value,

            "fiscal_year": fiscal_year,
            "period": period,
            "report_date": report_date,

            "currency": mapped_record.get("reported_currency"),
            "filing_date": mapped_record.get("filing_date"),
            "accepted_date": mapped_record.get("accepted_date"),
        })

    return facts


def extract_company_facts(ticker: str, company: str, statements: dict[str, list[dict]], periods: set[str] | None = None,) -> list[dict]:
    """
    Extract facts from all mapped financial statements.
    Expected input:
    {
        "income_statement": [mapped_record, ...],
        "balance_sheet": [mapped_record, ...],
        "cash_flow_statement": [mapped_record, ...]
    }

    If periods is None, all periods are included.
    Example: periods={"FY"} includes annual statements only.
    """

    all_facts = []

    for statement, records in statements.items():

        for record in records:

            if periods is  None or record.get("period")  in periods:
                    
                facts = extract_facts_from_record(
                    ticker=ticker,
                    company=company,
                    statement=statement,
                    mapped_record=record,
                )

                all_facts.extend(facts)

    return all_facts
