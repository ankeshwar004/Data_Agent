import os
import config
from utils.llm_picker import get_llm
from utils.prompts import extract_query_entities_prompt
from Models.schema import DataAgentSchema, QueryExtractionSchema
from agents.etl_agent import build_etl_graph
from agents.sql_agent import build_sql_graph

from database.coverage import check_requested_coverage

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
    """
    Inspects the database coverage for the requested datasets and periods.
    It's main purpose is to determine which data is available and which is missing, guiding the next steps in the data processing workflow.
    """

    coverage = check_requested_coverage(ticker=state.ticker,datasets=state.requested_datasets,required_years=state.required_periods)

    state.available_data = {
        dataset: result["available_years"]
        for dataset, result in coverage["datasets"].items()
    }

    state.missing_data = coverage["missing_data"]

    state.observations.append(
        f"coverage checked for {state.ticker}: "
        f"available_data={state.available_data}, "
        f"missing_data={state.missing_data}"
    )

    return state


def next_action_node(state: DataAgentSchema) -> DataAgentSchema:
    """
    Choose the next action from observed database state.
    """

    if not state.ticker:
        state.next_action = "fail"
        state.observations.append("Planning failed: ticker is missing.")
        return state

    if not state.requested_datasets:
        state.next_action = "fail"
        state.observations.append("Planning failed: no supported datasets requested.")
        return state

    if not state.missing_data:
        state.next_action = "query_database"
        state.observations.append("Plan: required data is available; query PostgreSQL.")
        return state

    if state.attempts >= state.max_attempts:
        state.next_action = "fail"
        last_etl_error = next(
            (
                observation
                for observation in reversed(state.observations)
                if observation.startswith("ETL result")
            ),
            None,
        )
        state.observations.append(
            "Plan: ETL retry budget exhausted."
            + (f" Last result: {last_etl_error}" if last_etl_error else "")
        )
        return state

    state.next_action = "fetch_missing_data"
    state.observations.append(f"Plan: fetch missing data: {state.missing_data}")

    return state


def etl_node(state: DataAgentSchema) -> DataAgentSchema:
    """
    Fetch missing financial data through the ETL specialist subgraph.
    """

    if state.attempts >= state.max_attempts:
        state.next_action = "fail"
        state.observations.append("ETL failed: retry budget exhausted.")
        return state
    
    state.attempts += 1
    etl_graph = build_etl_graph()

    for dataset, missing_years in state.missing_data.items():
        if dataset != "companies" and not missing_years:
            continue
        response = etl_graph.invoke(
            {
                "ticker": state.ticker,
                "dataset": dataset,
                "required_years": missing_years,
            }
        )
        response = response.model_dump() 
        outcome = response.get("outcome", None)
        result =  response.get("result", None)

        state.observations.append(
            f"ETL result for {dataset}: {result}; outcome={outcome}"
            f" ETL attempt: {state.attempts}"
        )

    state.next_action = "inspect_data"
    
    return state



def sql_node(state: DataAgentSchema) -> DataAgentSchema:
    """
    Routes the user's query to the SQL agent for processing.
    """
    query = state.user_query
    previous_sql = state.generated_sql_query
    previous_sql_error = state.sql_error or ""
    previous_verification_reason = state.verification_reason
    retry_context = (
        f"This is SQL attempt {state.sql_attempts + 1} of {state.max_sql_attempts}. "
        "Correct the previous query using the execution error and verification feedback. "
        "Do not repeat the same invalid query.\n"
        f"Previous SQL: {previous_sql}\n"
        f"SQL execution error: {previous_sql_error}\n"
        f"Verification feedback: {previous_verification_reason}"
    )

    state.sql_attempts += 1

    
    # Reset the previous attempt's status.
    state.sql_execution_success = False
    state.sql_error = None
    state.sql_query_result = ""
    state.generated_sql_query = ""
    state.final_answer = ""
    state.verification_passed = False
    state.verification_reason = ""
    
    sql_graph = build_sql_graph()
    response = sql_graph.invoke(
        {
            "user_query": query,
            "messages": [HumanMessage(content=query)],
            "generated_sql_query": previous_sql,
            "sql_execution_error": previous_sql_error,
            "prompt_query_context": retry_context,
        }
    )
    
    response = response.model_dump()  

    
    state.generated_sql_query = response.get("generated_sql_query", "")
    state.sql_query_result = response.get("sql_query_result", "")
    state.final_answer = response.get("final_answer", "")
    
    state.sql_execution_success = response.get("sql_execution_success", False)
    state.sql_error = response.get("sql_execution_error","")
    
    state.messages = state.messages + response.get("messages", [])
    
    state.observations.append(
        f"SQL agent attempt: {state.sql_attempts}, "
        f"generated_sql_query: {state.generated_sql_query}, "
    )
    
    state.next_action = "verify_result"
    
    return state



def verify_result_node(state):
    """
    Verifies the result of the SQL query execution and determines the next action based on the verification outcome.
    """
    if not state.sql_execution_success:
        state.verification_passed = False
        state.verification_reason = state.sql_error

    elif not state.final_answer.strip():
        state.verification_passed = False
        state.verification_reason = "SQL executed successfully, but no final answer was generated."
        
    elif not state.sql_query_result.strip():
        state.verification_passed = False
        state.verification_reason = "SQL executed successfully, but the query result is empty."

    else:
        state.verification_passed = True
        state.verification_reason = "SQL execution succeeded and a final answer was generated."

    state.observations.append(
        f"Verification passed: {state.verification_reason}"
        if state.verification_passed
        else f"Verification failed: {state.verification_reason}"
    )

    if state.verification_passed:
        state.next_action = "finish"

    elif state.sql_attempts < state.max_sql_attempts:
        state.next_action = "query_database"
        state.observations.append(f"Retrying SQL; attempt budget is {state.max_sql_attempts}.")

    else:
        state.next_action = "fail"
        state.observations.append("SQL attempt limit reached; stopping safely.")

    return state



def failure_node(state: DataAgentSchema) -> DataAgentSchema:
    """
    Handles failure scenarios and sets the final answer accordingly.
    """
    
    state.final_answer = f"""
    Could not process the request for ticker '{state.ticker}'
      Reason: {state.observations[-1] if state.observations else 'Unknown error'}"""

    state.next_action = "fail"
    return state



def build_data_agent_graph():
    """
    Builds and compiles the Data Agent graph.
    """
    
    graph = StateGraph(DataAgentSchema)

    graph.add_node("extract_query_entities", extract_query_entities)
    graph.add_node("inspect_data_node", inspect_data_node)
    graph.add_node("next_action_node", next_action_node)
    graph.add_node("etl_node", etl_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("verify_result_node", verify_result_node)
    graph.add_node("failure_node", failure_node)

    graph.add_edge(START, "extract_query_entities")
    
    graph.add_edge("extract_query_entities", "inspect_data_node")
    graph.add_edge("inspect_data_node", "next_action_node")

    def route_plan(state: DataAgentSchema):
        return state.next_action

    graph.add_conditional_edges(
        "next_action_node",route_plan,
        {
            "query_database": "sql_node",
            "fetch_missing_data": "etl_node",
            "fail": "failure_node",
        },)

    graph.add_edge("etl_node", "inspect_data_node")
    graph.add_edge("sql_node", "verify_result_node")

    def route_verification(state: DataAgentSchema):
        if state.next_action == "finish":
            return "finish"

        if state.next_action == "query_database":
            return "retry_sql"

        return "fail"

    graph.add_conditional_edges(
        "verify_result_node",route_verification,
        {
            "finish": END,
            "retry_sql": "sql_node",
            "fail": "failure_node",
        },)

    graph.add_edge("failure_node", END)

    return graph.compile()


if __name__ == "__main__":
    
    from IPython.display import Image, display
    img = Image(build_data_agent_graph().get_graph().draw_mermaid_png())
    
    os.makedirs(config.PNG_PATH, exist_ok=True)
    
    path = os.path.join(config.PNG_PATH, "data_agent_graph.png")
    with open(path, "wb") as f:
        f.write(img.data)