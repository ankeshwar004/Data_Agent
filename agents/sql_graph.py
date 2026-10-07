from langgraph.graph import END, START, StateGraph

from Models.schema import AgentSchema
from agents.sql_agent import (
    canceled_sql_query,
    curate_ques,
    execute_sql_query,
    generate_final_answer,
    generate_sql_query,
    is_sql_query_safe,
)


def is_safe_sql_edge(state: AgentSchema) -> str:
    """Choose whether to execute or cancel the generated SQL query."""
    if state.is_safe.casefold() == "yes":
        return "execute_sql"

    return "canceled_sql"


def build_sql_graph():
    """Build and compile the SQL agent graph."""
    graph = StateGraph(AgentSchema)

    graph.add_node("curate_ques", curate_ques)
    graph.add_node("generate_sql", generate_sql_query)
    graph.add_node("is_safe_sql", is_sql_query_safe)
    graph.add_node("canceled_sql", canceled_sql_query)
    graph.add_node("execute_sql", execute_sql_query)
    graph.add_node("represent_final_answer", generate_final_answer)

    graph.add_edge(START, "curate_ques")
    graph.add_edge("curate_ques", "generate_sql")
    graph.add_edge("generate_sql", "is_safe_sql")

    graph.add_conditional_edges(
        "is_safe_sql",
        is_safe_sql_edge,
        {
            "execute_sql": "execute_sql",
            "canceled_sql": "canceled_sql",
        },
    )

    graph.add_edge("canceled_sql", END)
    graph.add_edge("execute_sql", "represent_final_answer")
    graph.add_edge("represent_final_answer", END)

    return graph.compile()
