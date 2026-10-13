import os
import config

from utils.llm_picker import get_llm
from utils.etl_tools import ETLTools
from utils.prompts import etl_prompt
from Models.schema import ETLAgentSchema
from database.etl_service import fetch_and_load_financial_data

from langchain_core.messages import ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool



@tool
def extract_load_tool(url: str, output_folder: str, output_format: str)->str:
    """
    Tool function to extract data from a given URL and save it to the specified output path in the desired format.

    Args:
        url (str): The URL to extract data from.
        output_folder (str): The folder where the extracted data will be saved.
        output_format (str): The format in which to save the data ('csv' or 'json').
        
    Returns:
        str: A message indicating the success or failure of the extraction process.
    """
    etl_tools = ETLTools()
    return etl_tools.extract_load(url, output_folder, output_format)


@tool
def financial_etl(ticker: str, datasets: str, years: list[int])->str:
    """
    Tool function to fetch and load financial data for a given ticker, datasets, and years.
    """
    return fetch_and_load_financial_data(ticker=ticker, datasets=datasets, years=years)


def llm_node(state: ETLAgentSchema)-> ETLAgentSchema:
    """
    Processes the messages in the state using a language model (LLM) and updates the state with the response.
    Acts as a decision-making node that determines whether to invoke a tool or end the process based on the LLM's output.
    """
    
    messages = state.messages
    
    llm=get_llm("low")
    tools = [extract_load_tool, financial_etl]
    chain = etl_prompt | llm.bind_tools(tools)
    response = chain.invoke({ "messages": messages })
    
    state.messages=state.messages + [response]
    return state
    
    

def tool_node(state: ETLAgentSchema)-> ETLAgentSchema:
    """
    This node is responsible for invoking the appropriate tool based on the user's question and the context provided by the LLM.
    """
    
    tool_kits = [extract_load_tool, financial_etl]
    tools_result = []
    tool_by_name = {tool.name: tool for tool in tool_kits}
    
    tool_calls = getattr(state.messages[-1], "tool_calls", [])
    
    for tool_call in tool_calls:
        selected_tool = tool_by_name.get(tool_call["name"])
        if selected_tool is None:
            raise ValueError(f"Unknown ETL tool requested: {tool_call['name']}")
        observation = selected_tool.invoke(tool_call["args"])
        
        tools_result.append(
            ToolMessage(content=observation, tool_call_id=tool_call["id"])
        )
    
    state.messages=state.messages + tools_result
        
    return state


def build_etl_graph():
    """
    Builds a state graph for the ETL agent, defining the flow of states and transitions based on the agent's schema.
    """
    
    graph = StateGraph(ETLAgentSchema)
    
    graph.add_node("llm_node", llm_node)
    graph.add_node("tool_node", tool_node)
    
    
    def is_tool_call(state: ETLAgentSchema):
        tool_calls = getattr(state.messages[-1], "tool_calls", [])
        if tool_calls:
            return "tool_node"
        return "end"
    
    graph.add_edge(START, "llm_node")
    graph.add_conditional_edges(
        "llm_node",is_tool_call,
        {
            "tool_node": "tool_node",
            "end": END
        }
    )
    graph.add_edge("tool_node","llm_node")
    
    return graph.compile()


if __name__ == "__main__":
        
    from IPython.display import Image, display
    img = Image(build_etl_graph().get_graph().draw_mermaid_png())
    
    os.makedirs(config.PNG_PATH, exist_ok=True)
    path = os.path.join(config.PNG_PATH, "etl_agent_graph.png")
    with open(path, "wb") as f:
        f.write(img.data)