from utils.llm_picker import get_llm
from utils.etl_tools import ETLTools
from utils.prompts import routing_prompt
from Models.schema import DataAgentSchema, RouterSchema
from agents.etl_agent import build_etl_graph
from agents.sql_graph import build_sql_graph

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool


def router_node(state: DataAgentSchema) -> DataAgentSchema:
    """
    Determines whether to route the user's query to the SQL agent or the ETL agent based on the content of the query.
    """
    llm = get_llm("low").with_structured_output(RouterSchema)
    
    messages = state.messages[-1].content
    
    response_chain = routing_prompt | llm
    response = response_chain.invoke({"messages": messages}).model_dump()
    
    router_response = response.get("answer")
    
    state.router_response = router_response
     
    return state


def etl_node(state: DataAgentSchema) -> DataAgentSchema:
    """
    Routes the user's query to the ETL agent for processing.
    """
    messages = state.messages[-1].content
    
    etl_graph = build_etl_graph()
    response = etl_graph.invoke({"messages": [HumanMessage(content=f"Query: {messages}")]})
    
    state.messages = state.messages+ response["messages"]
    
    return state


def sql_node(state: DataAgentSchema) -> DataAgentSchema:
    """
    Routes the user's query to the SQL agent for processing.
    """
    messages = state.messages[-1].content
    
    sql_graph = build_sql_graph()
    response = sql_graph.invoke(
        {"user_query": messages, "messages": [HumanMessage(content=messages)]}
    )
    
    state.messages = state.messages + response["messages"]
    
    return state


def build_data_agent_graph():
    """
    Builds a state graph for the data agent, defining the flow of states and transitions based on the agent's schema.
    """
    graph = StateGraph(DataAgentSchema)
    
    graph.add_node("router_node", router_node)
    graph.add_node("etl_node", etl_node)
    graph.add_node("sql_node", sql_node)
    
    def is_sql_or_etl(state: DataAgentSchema):
        if state.router_response == "sql":
            return "sql_node"
        elif state.router_response == "etl":
            return "etl_node"
        else:
            return "END"
    
    graph.add_edge(START, "router_node")
    graph.add_conditional_edges(
        "router_node", is_sql_or_etl,
        {
            "sql_node": "sql_node",
            "etl_node": "etl_node",
            "END": END
        }
    )
    
    graph.add_edge("sql_node", END)
    graph.add_edge("etl_node", END)
    
    return graph.compile()