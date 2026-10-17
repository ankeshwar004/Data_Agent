from Models.schema import DataAgentSchema
from agents.data_agent import etl_node, next_action_node


def test_etl_stops_when_retry_limit_is_reached():
    state = DataAgentSchema(
        ticker="AAPL",
        requested_datasets=["income_statement"],
        required_periods=[2024],
        missing_data={"income_statement": [2024]},
        attempts=3,
        max_attempts=3,
        observations=[
            "ETL result for income_statement: "
            "{'success': False, 'error': 'API failed'}"
        ],
    )

    result = next_action_node(state)

    assert result.next_action == "fail"
    assert any(
        "retry budget exhausted" in observation.lower()
        for observation in result.observations
    )


def test_etl_is_attempted_when_retries_remain():
    state = DataAgentSchema(
        ticker="AAPL",
        requested_datasets=["income_statement"],
        required_periods=[2024],
        missing_data={"income_statement": [2024]},
        attempts=1,
        max_attempts=3,
    )

    result = next_action_node(state)

    assert result.next_action == "fetch_missing_data"


def test_etl_node_invokes_the_etl_subgraph(monkeypatch):
    calls = []

    class FakeETLGraph:
        def invoke(self, task):
            calls.append(task)
            return {
                "result": {
                    "success": True,
                    "missing_years": [],
                },
                "outcome": {
                    "status": "SUCCESS",
                },
            }

    monkeypatch.setattr(
        "agents.data_agent.build_etl_graph",
        lambda: FakeETLGraph(),
    )

    state = DataAgentSchema(
        ticker="AAPL",
        missing_data={"income_statement": [2024]},
    )

    result = etl_node(state)

    assert calls == [
        {
            "ticker": "AAPL",
            "dataset": "income_statement",
            "required_years": [2024],
        }
    ]
    assert "ETL result for income_statement" in result.observations[0]