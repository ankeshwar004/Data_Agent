from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from evals.deep_eval.trajectory_metrics import TraceRecorder, check_trace, numeric_match


def test_numeric_match_scales_and_tolerance():
    assert numeric_match("Revenue was $391,035,000,000", 391035000000)
    assert numeric_match("Revenue was $391.035 billion", 391035000000)
    assert numeric_match("Margin was 46.2%", 46.21)
    assert not numeric_match("Revenue was $10 million", 391035000000)


def test_numeric_match_booleans():
    assert numeric_match("Yes, the company was profitable.", True)
    assert not numeric_match("No, it reported a net loss.", True)
    assert numeric_match("No, it reported a net loss.", False)


class S(TypedDict, total=False):
    x: int


def _build(propagate: bool):
    def leaf(state: S, config: RunnableConfig) -> S:
        return {"x": 1}

    sub = StateGraph(S)
    sub.add_node("execute_sql", leaf)
    sub.add_edge(START, "execute_sql")
    sub.add_edge("execute_sql", END)
    sub_graph = sub.compile()

    def sql_node(state: S, config: RunnableConfig) -> S:
        return sub_graph.invoke(state, config=config) if propagate else sub_graph.invoke(state)

    g = StateGraph(S)
    g.add_node("sql_node", sql_node)
    g.add_edge(START, "sql_node")
    g.add_edge("sql_node", END)
    return g.compile()


def test_nested_spans_visible_with_explicit_config():
    # Explicit propagation is required on Python <3.11 and in async code; on 3.11+
    # sync calls also inherit via a context var, so only the positive case is asserted.
    rec = TraceRecorder()
    _build(True).invoke({}, config={"callbacks": [rec]})
    assert "execute_sql" in rec.names_under("sql_node")
    assert check_trace(rec, {"sql_attempt_results": [True]})["sql_traced"]
