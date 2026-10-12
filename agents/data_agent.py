from utils.llm_picker import get_llm
from utils.etl_tools import ETLTools
from utils.prompts import routing_prompt, extract_query_entities_prompt
from Models.schema import DataAgentSchema, RouterSchema, QueryExtractionSchema
from agents.etl_agent import build_etl_graph
from agents.sql_graph import build_sql_graph

from database.coverage import check_requested_coverage
from database.etl_service import fetch_and_load_financial_data

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool



def extract_query_entities(state: DataAgentSchema) -> DataAgentSchema:
    """
    Extracts ticker symbol, requested financial datasets, and periods/years
    from the user query using structured output.
    """
    query = state.user_query
    if not query and state.messages:
        query = state.messages[-1].content

    llm = get_llm("low").with_structured_output(QueryExtractionSchema)
    chain = extract_query_entities_prompt | llm
    extraction: QueryExtractionSchema = chain.invoke({"user_query": query})

    state.ticker = extraction.ticker.strip().upper()
    state.requested_datasets = list(extraction.datasets)
    state.required_periods = sorted(list(set(extraction.periods)))

    return state


def inspect_data_node(state: DataAgentSchema) -> DataAgentSchema:

    coverage = check_requested_coverage(ticker=state.ticker,datasets=state.requested_datasets,required_years=state.required_periods)

    state.available_data = {
        dataset: result["available_years"]
        for dataset, result in coverage["datasets"].items()
    }

    state.missing_data = coverage["missing_data"]

    state.observations.append(
        f"Database coverage checked for {state.ticker}: "
        f"complete={coverage['complete']}"
    )

    state.next_action = "query_database" if coverage["complete"] else "fetch_missing_data"

    return state



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
    """Fetch missing financial data using deterministic ETL."""

    if not state.ticker:
        state.observations.append("ETL failed: ticker is missing.")
        state.next_action = "fail"
        return state

    if not state.requested_datasets or not state.required_periods:
        state.observations.append( "ETL failed: requested datasets or years are missing.")
        state.next_action = "fail"
        return state

    all_success = True

    for dataset in state.requested_datasets:
        result = fetch_and_load_financial_data(ticker=state.ticker,dataset=dataset,required_years=state.required_periods)

        state.observations.append(f"ETL result for {dataset}: {result}")

        if not result["success"]:
            all_success = False

    if all_success:
        state.next_action = "inspect_data"
    else:
        state.next_action = "fail"

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
    
    graph.add_node("extract_query_entities", extract_query_entities)
    graph.add_node("inspect_data_node", inspect_data_node)
    graph.add_node("router_node", router_node)
    graph.add_node("etl_node", etl_node)
    graph.add_node("sql_node", sql_node)
    
    def route_request_type(state: DataAgentSchema):
        return "extract_query_entities" if state.router_response == "sql" else "etl_node"

    def route_after_inspection(state: DataAgentSchema):
        return "sql_node" if state.next_action == "query_database" else "etl_node"
    
    graph.add_edge(START, "router_node")
    graph.add_conditional_edges(
        "router_node", route_request_type,
        {
            "extract_query_entities": "extract_query_entities",
            "etl_node": "etl_node",
        }
    )
    graph.add_edge("extract_query_entities", "inspect_data_node")
    graph.add_conditional_edges(
        "inspect_data_node",
        route_after_inspection,
        {
            "sql_node": "sql_node",
            "etl_node": "etl_node",
        },
    )
    
    graph.add_edge("sql_node", END)
    graph.add_edge("etl_node", END)
    
    return graph.compile()