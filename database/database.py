from database.connection import DatabaseConnection
from psycopg import sql
from psycopg.errors import QueryCanceled
from typing import Tuple
import re



class DatabaseUtils:

    def __init__(self, connection: DatabaseConnection):
        self.connection = connection


    def schema_details(self,schema_name: str, include_sample_data: bool = True)-> str:
        """
        Retrieves the schema details for the specified schema name, including table names, column names, data types,
        and optionally sample data.
        """
        
        schema_details=[]
        schema_details.append(f"Database Schema Details for '{schema_name}':")
        
        with self.connection.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    ORDER BY table_name;
                    """,
                    (schema_name,),
                )
                tables=cur.fetchall()
                
                for table in tables:
                    table_name = table["table_name"]
                    schema_details.append(f"Table: {table_name}")
                    
                    cur.execute(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = %s and table_name = %s
                        ORDER BY ordinal_position;
                        """, 
                        (schema_name, table_name)
                    )
                    
                    details=cur.fetchall()
                    
                    for detail in details:
                        column = detail["column_name"]
                        data_type = detail["data_type"]
                        schema_details.append(f"  Column: {column}, Data Type: {data_type}")
                        
                    query=sql.SQL("SELECT COUNT(*) FROM {}.{};").format(
                        sql.Identifier(schema_name),
                        sql.Identifier(table_name)
                    )
                    
                    cur.execute(query)
                    schema_details.append(f" Total Rows: {cur.fetchone()['count']}")
                    
                    if include_sample_data:
                                            
                        sample_query=sql.SQL("SELECT * FROM {}.{} LIMIT 2;").format(
                            sql.Identifier(schema_name),
                            sql.Identifier(table_name)
                        )
                        
                        cur.execute(sample_query)
                        
                        for row in cur.fetchall():
                            schema_details.append(f" Sample Row: {row}")
                    
                    
        return "\n".join(schema_details)
    
    
    
    def execute_sql_query(self, query: str)-> tuple[bool, list[dict] | str ]:
        """
        Executes the provided SQL query if it is a valid read-only query and returns the result.
        """
        normalized = query.strip()
        try:
            if ";" in normalized.rstrip(";"):
                raise ValueError("Multiple SQL statements are not permitted.")
            
            with self.connection.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    
                    cur.execute("SELECT set_config('statement_timeout', %s, true)",("5000ms",))  # Set a 5-second timeout for the query execution

                    cur.execute(query)

                    if cur.description:           # if the query returns rows (e.g., SELECT), fetch and return them
                        return True , cur.fetchall()

                    return True , "No data returned from the query."  

        except QueryCanceled as e:
            print("Query canceled due to timeout.")
            return False , "Query canceled due to timeout."
        
        except Exception as e:
            print(f"Error executing SQL query: {e}")
            return False , str(e)
        

      