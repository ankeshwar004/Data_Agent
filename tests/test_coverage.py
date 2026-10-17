from contextlib import contextmanager

from database import coverage


class FakeCursor:
    def __init__(self):
        self.query = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=None):
        self.query = str(query)
        self.params = params or ()

    def fetchone(self):
        # Simulate the company existing.
        if "SELECT company_id" in self.query:
            return {"company_id": 1}
        return None

    def fetchall(self):
        # Simulate financial records for 2022 and 2024.
        if "SELECT DISTINCT fiscal_year" in self.query:
            return [
                {"fiscal_year": 2022},
                {"fiscal_year": 2024},
            ]
        return []


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self):
        return FakeCursor()


class FakePool:
    @contextmanager
    def connection(self):
        yield FakeConnection()


class FakeDatabaseConnection:
    pool = FakePool()


def test_detects_missing_years(monkeypatch):
    monkeypatch.setattr(
        coverage, "db_connection", FakeDatabaseConnection()
    )

    result = coverage.check_company_financial_coverage(
        ticker="aapl",
        dataset="income_statement",
        required_years=[2022, 2023, 2024],
    )

    assert result["ticker"] == "AAPL"
    assert result["available_years"] == [2022, 2024]
    assert result["missing_years"] == [2023]
    assert result["complete"] is False


def test_all_requested_years_are_available(monkeypatch):
    monkeypatch.setattr(
        coverage, "db_connection", FakeDatabaseConnection()
    )

    result = coverage.check_company_financial_coverage(
        ticker="AAPL",
        dataset="income_statement",
        required_years=[2022, 2024],
    )

    assert result["missing_years"] == []
    assert result["complete"] is True


def test_rejects_unsupported_dataset():
    import pytest

    with pytest.raises(ValueError, match="Unsupported dataset"):
        coverage.check_company_financial_coverage(
            ticker="AAPL",
            dataset="invalid_dataset",
            required_years=[2024],
        )