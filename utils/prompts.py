from langchain_core.prompts import ChatPromptTemplate, PromptTemplate


prompt_generate_sql_query = ChatPromptTemplate.from_messages([
    ("system",
     """
        You are an SQL analyst agent. Your task is to convert the user's natural language 
        query into Postgres SQL query that can be executed on the database. You are provided 
        with the user's original query and the schema details of the database, including
        table names, column names, data types, and sample data for each table so that 
        you can understand the structure of the database and generate an accurate SQL query.
        Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
        Note - Just generate the SQL query without any explanation or additional text because
        this query will be executed directly on the database. So, the output should be SQL
        ready to be executed without any modifications.
    """),
    ("human", 
     """
        User's original query: {curated_ques}
        Schema details: {schema_info}
    """)
])


sql_query_judge_prompt = PromptTemplate.from_template(
    """
     You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
    safe or not. The SQL query should only be used for data retrieval and should not modify the 
    database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
    database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
    the structure or content of the database. If the SQL query is safe, respond with 'Yes' otherwise respond with 
    'No'. Additionally, provide comments explaining your decision.
    Here's the SQL query to evaluate: {sql_query}
    """)


final_answer_prompt = PromptTemplate.from_template(
    """
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {query_result}
    Here is the user's original question: {curated_ques}
    """)


curate_question_prompt = PromptTemplate.from_template(
    """
    You are a question curator for a database query agent.

    Your job is to transform the user's natural-language question into a
    clear, precise, database-oriented question that can be answered using
    the available database.

    Rules:
    1. Preserve the user's original intent.
    2. Remove unnecessary wording and conversational language.
    3. Clarify obvious temporal expressions such as "last month",
    "this year", or "yesterday".
    4. Identify important entities, metrics, filters, comparisons,
    aggregations, and time ranges mentioned by the user.
    5. Do NOT invent information that the user did not provide.
    6. Do NOT assume an undefined business meaning. For example,
    "best drivers" should not automatically mean highest-rated drivers.
    7. If the question is genuinely ambiguous, preserve the ambiguity
    and explicitly indicate what information is missing.
    8. Do not generate SQL.
    9. Return only the curated question.

    User question:
    {user_question}
    """)



transform_load_prompt = PromptTemplate.from_template(
    """
    You are a Python Data Analyst who uses Pandas to analyze data. 
    You need to provide only the Pandas Code that will help to perform the right ETL operations on the data stored in the file : {input_file_path}
    as per the user's question. Do not provide any explanation or comments, only
    the code should be provided. The code should be in a format that can be executed 
    in a Python environment with Pandas installed. 
    Don't write anything else than Pandas Code. \n
    
    Create the Pandas Dataframe from the data stored in the file : {input_file_path} and then 
    write the code to transform and save the data at {output_folder}.
    Here's the user's question: {user_question}\n
    Here's the context of the data you will be analyzing: {context_row}\n 
    """)


etl_prompt = PromptTemplate.from_template(
    """
    You are a Python Data Analyst who has access to tools that can extract and load, 
    transform and load data. You will be provided with a user's question 
    and you would need to perform the right ETL operations as per the user's question. 
    If the operation is performed then inform the user and end the coversation.
    Here's the chat history: {messages}\n

    """)


routing_prompt = PromptTemplate.from_template(
    """
    query={messages}
    You are a routing agent that decides whether the user's question should be handled by the SQL agent or the ETL agent.
    """)
    
    
    