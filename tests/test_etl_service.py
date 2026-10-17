import database.etl_service as etl


def test_etl_filters_unrequested_years_and_non_annual_records(
    monkeypatch,
):
    # Pretend 2023 and 2024 are missing initially.
    coverage_results = [
        {
            "complete": False,
            "missing_years": [2023, 2024],
        },
        {
            "complete": True,
            "missing_years": [],
        },
    ]

    def fake_coverage(*args, **kwargs):
        return coverage_results.pop(0)

    class FakeFMPClient:
        def fetch(self, endpoint, ticker, limit):
            return [
                {"fiscalYear": "2023", "period": "FY", "revenue": 100},
                {"fiscalYear": "2023", "period": "FY", "revenue": 110},
                {"fiscalYear": "2023", "period": "Q4", "revenue": 90},
                {"fiscalYear": "2024", "period": "FY", "revenue": 120},
                {"fiscalYear": "2022", "period": "FY", "revenue": 80},
                {"fiscalYear": "invalid", "period": "FY", "revenue": 1},
            ]

    loaded_records = []

    monkeypatch.setattr(
        etl, "check_company_financial_coverage", fake_coverage
    )
    monkeypatch.setattr(etl, "FMPClient", FakeFMPClient)
    monkeypatch.setattr(
        etl, "ensure_company_profile", lambda client, ticker: 1
    )

    monkeypatch.setitem(
        etl.DATASETS_CONFIG,
        "income_statement",
        {
            "endpoint": "income-statement",
            "mapper": lambda record: record,
            "upsert": lambda company_id, mapped:
                loaded_records.append(mapped),
        },
    )

    result = etl.fetch_and_load_financial_data(
        ticker="aapl",
        dataset="income_statement",
        required_years=[2023, 2024],
    )

    assert result["success"] is True
    assert result["loaded_records"] == 2
    assert {
        record["fiscalYear"] for record in loaded_records
    } == {"2023", "2024"}
    assert all(
        record["period"] == "FY"
        for record in loaded_records
    )
    
    
def test_etl_reports_api_failure(monkeypatch):
    class BrokenFMPClient:
        def fetch(self, endpoint, ticker, limit):
            raise RuntimeError("Simulated API failure")

    monkeypatch.setattr(
        etl,
        "check_company_financial_coverage",
        lambda *args, **kwargs: {
            "complete": False,
            "missing_years": [2024],
        },
    )
    monkeypatch.setattr(etl, "FMPClient", BrokenFMPClient)
    monkeypatch.setattr(
        etl, "ensure_company_profile", lambda client, ticker: 1
    )

    result = etl.fetch_and_load_financial_data(
        ticker="AAPL",
        dataset="income_statement",
        required_years=[2024],
    )

    assert result["success"] is False
    assert "Simulated API failure" in result["error"]