import os
import config

from database.database import DatabaseUtils
from database.connection import pool
from Models.schema import AgentSchema, JudgeSchema
from utils.llm_picker import get_llm
from utils.prompts import prompt_generate_sql_query , sql_query_judge_prompt, final_answer_prompt, curate_question_prompt
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser



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
    
    database_obj = DatabaseUtils(pool)
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
    state.final_answer=f"SQL Query is not safe to execute. Comments: {comments}"
    state.messages=state.messages + [AIMessage(content=f"{state.final_answer}")]
    
    return state



def execute_sql_query(state: AgentSchema)-> AgentSchema:
    """
    Executes the generated SQL query and stores the result in the state.
    """
    sql_query=state.generated_sql_query
    
    database_obj = DatabaseUtils(pool)
    result = database_obj.execute_sql_query(sql_query)
    
    state.sql_query_result=str(result)
    
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


