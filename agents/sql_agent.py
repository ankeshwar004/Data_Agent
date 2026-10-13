import os
import config

from database.database import DatabaseUtils
from database.connection import db_connection

from Models.schema import AgentSchema, JudgeSchema
from utils.llm_picker import get_llm
from utils.prompts import prompt_generate_sql_query , sql_query_judge_prompt, final_answer_prompt, curate_question_prompt

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, START, StateGraph




def curate_ques(state:AgentSchema)-> AgentSchema:
    """
    Curate( cureate mean  to make clear, structured, and useful ) the user's question to make it clear, structured, and useful for
    the next step.
    """
    user_query=state.user_query
    llm=get_llm("low")
    
    response_chain = curate_question_prompt | llm | StrOutputParser()
    response = response_chain.invoke({ "user_question": user_query })
    
    state.curated_ques=response
    state.messages=state.messages + [HumanMessage(content=f"{response}")] # check late if this correct  or add response in AIMessage 
    
    return state

    

def generate_sql_query(state: AgentSchema)-> AgentSchema:
    """
    Generates an SQL query based on the curated question and the schema details of the database.
    """
    
    curated_ques=state.curated_ques
    
    database_obj = DatabaseUtils(db_connection)
    schema_details = database_obj.schema_details(config.DATABASE_SCHEMA, include_sample_data=True)
    
    llm=get_llm("low")
    
    chain = prompt_generate_sql_query | llm | StrOutputParser()
    response = chain.invoke({ "curated_ques": curated_ques, "schema_info": schema_details })
    
    state.generated_sql_query=response
    
    return state
    


def is_sql_query_safe(state: AgentSchema)-> AgentSchema:
    """
    Checks whether the generated SQL query is safe to execute or not.
    """
    
    sql_query=state.generated_sql_query
    
    llm=get_llm("low")
    llm_judge = llm.with_structured_output(JudgeSchema)
    
    chain = sql_query_judge_prompt | llm_judge
    response = chain.invoke({ "sql_query": sql_query })  
    
    state.is_safe = response.is_safe  
    state.comments = response.comments
    
    return state



def canceled_sql_query(state: AgentSchema)-> AgentSchema:
    """
    Cancels the execution of the SQL query and provides a final answer.
    """
    
    comments=state.comments
    state.sql_execution_success = False
    state.final_answer=f"SQL Query is not safe to execute. Comments: {comments}"
    state.messages=state.messages + [AIMessage(content=f"{state.final_answer}")]
    
    return state



def execute_sql_query(state: AgentSchema)-> AgentSchema:
    """
    Executes the generated SQL query and stores the result in the state.
    """
    sql_query=state.generated_sql_query
    
    database_obj = DatabaseUtils(db_connection)
    success,result = database_obj.execute_sql_query(sql_query)
    
    if success:
        state.sql_query_result=str(result)
        state.sql_execution_success = True
        state.sql_execution_error = None
        
    else:
        state.sql_query_result=""
        state.sql_execution_success = False
        state.sql_execution_error = result  # Store the error message in the state
        
        
    return state


def generate_final_answer(state: AgentSchema)-> AgentSchema:
    """
    Generates a final answer based on the execution result of the SQL query and the user's original question.
    """
    curated_ques=state.curated_ques
    sql_query_result=state.sql_query_result
    
    llm=get_llm("low")
        
    response_chain = final_answer_prompt | llm | StrOutputParser()
    response = response_chain.invoke({ "curated_ques": curated_ques, "query_result": sql_query_result })
    
    state.final_answer=response
    state.messages=state.messages + [AIMessage(content=f"{response}")]
    
    return state




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
    
    def is_safe_sql_edge(state: AgentSchema) -> str:
        if state.is_safe == "Yes":
            return "execute_sql"

        return "canceled_sql"

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


if __name__ == "__main__":
       
    from IPython.display import Image, display
    img = Image(build_sql_graph().get_graph().draw_mermaid_png())
    os.makedirs(config.PNG_PATH, exist_ok=True)
    
    path = os.path.join(config.PNG_PATH, "sql_agent_graph.png")
    with open(path, "wb") as f:
        f.write(img.data)