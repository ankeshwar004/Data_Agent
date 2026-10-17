from contextlib import contextmanager

from database.database import DatabaseUtils


class FakeCursor:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.description = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=None):
        query = str(query)

        if query == "SELECT 1":
            if self.should_fail:
                raise RuntimeError("Simulated database error")

            self.description = [("result",)]
            self.rows = [{"result": 1}]

    def fetchmany(self, size):
        rows = self.rows[:size]
        self.rows = self.rows[size:]
        return rows

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self):
        return FakeCursor(self.should_fail)


class FakePool:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    @contextmanager
    def connection(self):
        yield FakeConnection(self.should_fail)


class FakeDatabaseConnection:
    def __init__(self, should_fail=False):
        self.pool = FakePool(should_fail)


def test_sql_execution_success():
    database = DatabaseUtils(FakeDatabaseConnection())

    success, result = database.execute_sql_query("SELECT 1")

    assert success is True
    assert result == [{"result": 1}]


def test_sql_execution_failure():
    database = DatabaseUtils(
        FakeDatabaseConnection(should_fail=True)
    )

    success, result = database.execute_sql_query("SELECT 1")

    assert success is False
    assert "Simulated database error" in result