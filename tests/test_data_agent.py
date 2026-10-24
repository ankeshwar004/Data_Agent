from Models.schema import DataAgentSchema, VerificationSchema
from agents.data_agent import etl_node, next_action_node, verify_result_node

from langchain_core.runnables import RunnableLambda


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


# --- verify_result_node tests ---

def test_verify_fails_when_sql_execution_failed():
    """Stage 1: execution failure skips LLM verifier."""
    state = DataAgentSchema(
        user_query="What was AAPL revenue in 2024?",
        sql_execution_success=False,
        sql_error="relation does not exist",
        sql_attempts=1,
        max_sql_attempts=3,
    )

    result = verify_result_node(state)

    assert result.verification_passed is False
    assert "SQL execution failed" in result.verification_reason
    assert result.next_action == "query_database"


def test_verify_fails_when_no_final_answer():
    """Stage 1: empty final_answer triggers retry."""
    state = DataAgentSchema(
        user_query="What was AAPL revenue in 2024?",
        sql_execution_success=True,
        sql_query_result=[{"revenue": 100000}],
        final_answer="",
        sql_attempts=1,
        max_sql_attempts=3,
    )

    result = verify_result_node(state)

    assert result.verification_passed is False
    assert "no final answer" in result.verification_reason.lower()
    assert result.next_action == "query_database"


def test_verify_passes_with_llm_approval(monkeypatch):
    """Stage 2: LLM verifier approves correct answer."""

    class FakeLLM:
        def with_structured_output(self, schema):
            return RunnableLambda(
                lambda _: schema(
                    sql_targets_correct_data=True,
                    answer_supported_by_result=True,
                    passed=True,
                    reason="All checks passed.",
                )
            )

    monkeypatch.setattr(
        "agents.data_agent.get_llm",
        lambda *a, **kw: FakeLLM(),
    )

    state = DataAgentSchema(
        user_query="What was AAPL revenue in 2024?",
        sql_execution_success=True,
        generated_sql_query="SELECT revenue FROM income_statements WHERE ticker='AAPL' AND fiscal_year=2024",
        sql_query_result=[{"revenue": 100000}],
        final_answer="Apple's revenue in 2024 was $100,000.",
        sql_attempts=1,
        max_sql_attempts=3,
    )

    result = verify_result_node(state)

    assert result.verification_passed is True
    assert result.next_action == "finish"


def test_verify_rejects_wrong_answer(monkeypatch):
    """Stage 2: LLM verifier rejects inaccurate answer."""

    class FakeLLM:
        def with_structured_output(self, schema):
            return RunnableLambda(
                lambda _: schema(
                    sql_targets_correct_data=True,
                    answer_supported_by_result=False,
                    passed=False,
                    reason="Answer claims revenue was $200k but result shows $100k.",
                )
            )

    monkeypatch.setattr(
        "agents.data_agent.get_llm",
        lambda *a, **kw: FakeLLM(),
    )

    state = DataAgentSchema(
        user_query="What was AAPL revenue in 2024?",
        sql_execution_success=True,
        generated_sql_query="SELECT revenue FROM income_statements WHERE ticker='AAPL' AND fiscal_year=2024",
        sql_query_result=[{"revenue": 100000}],
        final_answer="Apple's revenue in 2024 was $200,000.",
        sql_attempts=1,
        max_sql_attempts=3,
    )

    result = verify_result_node(state)

    assert result.verification_passed is False
    assert result.next_action == "query_database"


def test_verify_empty_result_does_not_auto_retry(monkeypatch):
    """Empty SQL result (zero rows) should reach Stage 2, not auto-retry."""

    class FakeLLM:
        def with_structured_output(self, schema):
            return RunnableLambda(
                lambda _: schema(
                    sql_targets_correct_data=True,
                    answer_supported_by_result=True,
                    passed=True,
                    reason="Query is correct; no data exists for requested period.",
                )
            )

    monkeypatch.setattr(
        "agents.data_agent.get_llm",
        lambda *a, **kw: FakeLLM(),
    )

    state = DataAgentSchema(
        user_query="What was AAPL revenue in 1990?",
        sql_execution_success=True,
        generated_sql_query="SELECT revenue FROM income_statements WHERE ticker='AAPL' AND fiscal_year=1990",
        sql_query_result=[],
        final_answer="No revenue data is available for Apple in 1990.",
        sql_attempts=1,
        max_sql_attempts=3,
    )

    result = verify_result_node(state)

    assert result.verification_passed is True
    assert result.next_action == "finish"


def test_verify_fails_to_finish_when_attempts_exhausted():
    """Verification failure at max attempts routes to fail, not retry."""
    state = DataAgentSchema(
        user_query="What was AAPL revenue in 2024?",
        sql_execution_success=False,
        sql_error="timeout",
        sql_attempts=3,
        max_sql_attempts=3,
    )

    result = verify_result_node(state)

    assert result.verification_passed is False
    assert result.next_action == "fail"


def test_verify_accepts_on_verifier_error(monkeypatch):
    """If the LLM verifier itself errors, accept the result (fallback)."""

    class BrokenLLM:
        def with_structured_output(self, schema):
            return RunnableLambda(lambda _: (_ for _ in ()).throw(RuntimeError("LLM down")))

    monkeypatch.setattr(
        "agents.data_agent.get_llm",
        lambda *a, **kw: BrokenLLM(),
    )

    state = DataAgentSchema(
        user_query="What was AAPL revenue in 2024?",
        sql_execution_success=True,
        generated_sql_query="SELECT revenue FROM income_statements",
        sql_query_result=[{"revenue": 100000}],
        final_answer="Apple's revenue was $100,000.",
        sql_attempts=1,
        max_sql_attempts=3,
    )

    result = verify_result_node(state)

    assert result.verification_passed is True
    assert result.next_action == "finish"
    assert "Verifier error" in result.verification_reason
