
def map_company_profile(record: dict) -> dict:
     return {
        "ticker": record.get("symbol"),
        "company_name": record.get("companyName"),
        "cik": record.get("cik"),
        "isin": record.get("isin"),
        "cusip": record.get("cusip"),
        "exchange": record.get("exchange"),
        "exchange_full_name": record.get("exchangeFullName"),
        "currency": record.get("currency"),
        "sector": record.get("sector"),
        "industry": record.get("industry"),
        "website": record.get("website"),
        "description": record.get("description"),
        "ceo": record.get("ceo"),
        "country": record.get("country"),
        "market_cap": record.get("marketCap"),
        "current_price": record.get("price"),
        "beta": record.get("beta"),
        "last_dividend": record.get("lastDividend"),
        "ipo_date": record.get("ipoDate"),
        "is_actively_trading": record.get("isActivelyTrading"),
        "raw_payload": record,
    }


def map_income_statement(record: dict) -> dict:
     return {
        "report_date": record.get("date"),
        "fiscal_year": record.get("fiscalYear"),
        "period": record.get("period"),
        "reported_currency": record.get("reportedCurrency"),
        "filing_date": record.get("filingDate"),
        "accepted_date": record.get("acceptedDate"),
        "revenue": record.get("revenue"),
        "cost_of_revenue": record.get("costOfRevenue"),
        "gross_profit": record.get("grossProfit"),
        "operating_expenses": record.get("operatingExpenses"),
        "operating_income": record.get("operatingIncome"),
        "ebit": record.get("ebit"),
        "ebitda": record.get("ebitda"),
        "income_before_tax": record.get("incomeBeforeTax"),
        "income_tax_expense": record.get("incomeTaxExpense"),
        "net_income": record.get("netIncome"),
        "eps": record.get("eps"),
        "eps_diluted": record.get("epsDiluted"),

        # Preserve every original FMP key-value pair.
        "raw_payload": record,
    }


def map_balance_sheet(record: dict) -> dict:
     return {
        "report_date": record.get("date"),
        "fiscal_year": record.get("fiscalYear"),
        "period": record.get("period"),
        "reported_currency": record.get("reportedCurrency"),
        "filing_date": record.get("filingDate"),
        "accepted_date": record.get("acceptedDate"),
        "cash_and_cash_equivalents": record.get("cashAndCashEquivalents"),
        "total_current_assets": record.get("totalCurrentAssets"),
        "total_assets": record.get("totalAssets"),
        "total_current_liabilities": record.get("totalCurrentLiabilities"),
        "total_liabilities": record.get("totalLiabilities"),
        "total_stockholders_equity": record.get("totalStockholdersEquity"),
        "total_equity": record.get("totalEquity"),
        "total_debt": record.get("totalDebt"),
        "net_debt": record.get("netDebt"),
        "raw_payload": record,
    }


def map_cash_flow_statement(record: dict) -> dict:
     return {
        "report_date": record.get("date"),
        "fiscal_year": record.get("fiscalYear"),
        "period": record.get("period"),
        "reported_currency": record.get("reportedCurrency"),
        "filing_date": record.get("filingDate"),
        "accepted_date": record.get("acceptedDate"),
        "net_income": record.get("netIncome"),
        "operating_cash_flow": record.get("operatingCashFlow"),
        "investing_cash_flow": record.get("investingCashFlow"),
        "financing_cash_flow": record.get("financingCashFlow"),
        "capital_expenditure": record.get("capitalExpenditure"),
        "free_cash_flow": record.get("freeCashFlow"),
        "net_change_in_cash": record.get("netChangeInCash"),
        "raw_payload": record,
    }