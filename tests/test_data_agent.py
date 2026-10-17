from Models.schema import DataAgentSchema
from agents.data_agent import next_action_node


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