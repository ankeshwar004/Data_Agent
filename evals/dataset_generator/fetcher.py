import json
import logging
import random
from datetime import datetime, timezone

from fmp_client import FMPClient

from config import (
    FIXTURE_DIR,
    NUM_COMPANIES,
    STATEMENT_LIMIT
)

logger = logging.getLogger(__name__)


class DatasetFetcher:

    def __init__(self):
        self.client = FMPClient()
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    def get_company_universe(self)-> list:
        """
        Fetches the list of all available stock symbols from the Financial Modeling Prep API.
        """

        url = f"{self.client.BASE_URL}/stock-list"

        response = self.client.session.get(url, params={"apikey": self.client.api_key}, timeout=30)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError("Invalid stock-list response")

        symbols = {item["symbol"] for item in data if item.get("symbol")}

        return sorted(symbols)
    

    def select_companies(self, seed=42) -> list:
        """
        Selects a random sample of companies from the available stock symbols.
        """

        symbols = self.get_company_universe()

        rng = random.Random(seed)

        return rng.sample(symbols, min(NUM_COMPANIES, len(symbols)))
    

    def fetch_company_data(self, ticker: str) -> dict:
        """
        Fetches the profile and financial statements for a given company ticker.
        """

        profile = self.client.fetch("profile", ticker, limit=1)[0]
        company_name = profile.get("companyName")

        statements = {}

        for name, endpoint in [
            ("income_statement", "income-statement"),
            ("balance_sheet", "balance-sheet-statement"),
            ("cash_flow_statement", "cash-flow-statement")
        ]:
            statements[name] = self.client.fetch(endpoint, ticker, limit=STATEMENT_LIMIT)

        return {
            "ticker": ticker,
            "company_name": company_name,
            "profile": profile,
            "statements": statements
        }

    def save_fixture(self, ticker, data):
        """
        Saves the fetched company data to a JSON fixture file.
        """
        path = FIXTURE_DIR / f"{ticker}.json"

        payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data": data
        }

        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def run(self) -> list[dict]:
        """
        Fetches data for a random sample of companies and saves them as JSON fixtures.
        """
        
        selected = self.select_companies()

        results = []

        for ticker in selected:
            try:
                data = self.fetch_company_data(ticker)

                self.save_fixture(ticker, data)

                results.append(data)

                logger.info("Fetched %s", ticker)
                
            except Exception as exc:
                logger.warning("Skipped %s: %s", ticker, exc)

        return results