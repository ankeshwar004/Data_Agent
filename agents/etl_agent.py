from utils.llm_picker import get_llm
from utils.etl_tools import ETLTools
from utils.prompts import transform_load_prompt, etl_prompt
from Models.schema import ETLAgentSchema

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
def transform_load_tool(input_file_path: str, output_folder: str, output_format: str, user_question: str)->str:
    """
    Tool function to transform data from a given input file and save it to the specified output path in the desired format.

    Args:
        input_file_path (str): The path to the input file containing the data to be transformed.
        output_folder (str): The folder where the transformed data will be saved.
        output_format (str): The format in which to save the data ('csv' or 'json').
        user_question (str): The user's original query that needs to be answered by the agent.
        
    Returns:
        str: A message indicating the success or failure of the transformation process.
    """
    etl_tools = ETLTools()
    context_row = etl_tools.transform_load_context(input_file_path)
    
    llm = get_llm("low")
    chain = transform_load_prompt | llm
    response = chain.invoke({
        "input_file_path": input_file_path,
        "output_folder": output_folder,
        "output_format": output_format,
        "user_question": user_question,
        "context_row": context_row
    }).content
    
    pandas_code = response.strip().strip('```').strip().lstrip('python').strip()
    
    # Execute the generated Pandas code
    result = etl_tools.execute_code(pandas_code)
    
    return f"Data transformed and saved to {output_folder} in {output_format.upper()} format. Execution result: {result}"





def llm_node(state: ETLAgentSchema)-> ETLAgentSchema:
    """
    Processes the messages in the state using a language model (LLM) and updates the state with the response.
    """
    
    messages = state.messages
    
    llm=get_llm("low")
    tools = [extract_load_tool, transform_load_tool]
    chain = etl_prompt | llm.bind_tools(tools)
    response = chain.invoke({ "messages": messages })
    
    state.messages=state.messages + [response]
    return state
    
    

def tool_node(state: ETLAgentSchema)-> ETLAgentSchema:
    """
    This node is responsible for invoking the appropriate tool based on the user's question and the context provided by the LLM.
    """
    
    tool_kits = [extract_load_tool, transform_load_tool]
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


def build_etl_graph()->ETLAgentSchema:
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