from langchain_core.runnables import RunnableLambda

from Models.schema import AgentSchema, JudgeSchema
from agents.sql_agent import is_sql_query_safe, canceled_sql_query

def test_rejected_sql_returns_safety_message():
    state = AgentSchema(
        generated_sql_query="DROP TABLE companies",
        is_safe="No",
        comments="Query attempts to modify the database.",
    )

    result = canceled_sql_query(state)

    assert result.sql_execution_success is False
    assert "not safe to execute" in result.final_answer.lower()
    assert "modify the database" in result.final_answer
    
    

def test_llm_judge_rejection_is_recorded(monkeypatch):
    class FakeLLM:
        def with_structured_output(self, schema):
            return RunnableLambda(
                lambda _: schema(
                    is_safe="No",
                    comments="Query attempts to modify data.",
                )
            )

    monkeypatch.setattr(
        "agents.sql_agent.get_llm",
        lambda *_args, **_kwargs: FakeLLM(),
    )

    state = AgentSchema(
        generated_sql_query="DELETE FROM companies"
    )

    result = is_sql_query_safe(state)

    assert result.is_safe == "No"
    assert "modify data" in result.comments