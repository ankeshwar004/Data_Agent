import os
import requests
import config



class FMPClient:
    
    BASE_URL = config.FMP_BASE_URL
    
    def __init__(self):
        
        self.api_key = os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is not configured")

        self.session = requests.Session()

    def fetch(self, endpoint: str, ticker: str, limit: int = 5):
        
        """
        Fetches data from the Financial Modeling Prep API for a given endpoint and ticker.
        
        Args:
            endpoint (str): The FMP endpoint to query (e.g., "profile", "income-statement").
            ticker (str): The stock ticker symbol.
            limit (int): The maximum number of records to return (default is 5).

        Returns:
            list: A list of dictionaries representing the fetched data.
        
        Raises:
            ValueError: If the ticker is invalid or the endpoint is unsupported.
            RuntimeError: If the API returns an error or an unexpected response format.

        """


        if not ticker.strip():
            raise ValueError("Invalid ticker")

        allowed_endpoints = {
            "profile",
            "income-statement",
            "balance-sheet-statement",
            "cash-flow-statement",
        }
        if endpoint not in allowed_endpoints:
            raise ValueError("Unsupported FMP endpoint")

        params = {
            "symbol": ticker,
            "apikey": self.api_key,
            "limit": limit
        }

        response = self.session.get(f"{self.BASE_URL}/{endpoint}",params=params,timeout=20)
        
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError("Unexpected FMP response error: expected a list of records")

        if not data:
            raise ValueError(
                f"No {endpoint} records returned for {ticker}"
            )

        return data
    
    
#  small test for the FMPClient class
if __name__ == "__main__":
    client = FMPClient()
    try:
        profile_data = client.fetch("profile", "AAPL")
        print("Profile Data:", profile_data)
        
        income_statement_data = client.fetch("income-statement", "AAPL")
        print("Income Statement Data:", income_statement_data)
        
        balance_sheet_data = client.fetch("balance-sheet-statement", "AAPL")
        print("Balance Sheet Data:", balance_sheet_data)
        
        cash_flow_data = client.fetch("cash-flow-statement", "AAPL")
        print("Cash Flow Data:", cash_flow_data)
        
    except Exception as e:
        print(f"Error: {e}")