from database.connection import pool


class DatabaseUtils:
    
    def __init__(self,pool):
        self.pool=pool
        
    def schema_details(self,schema_name: str, include_sample_data: bool = True):
        
        schema_details=[]
        schema_details.append(f"Database Schema Details for '{schema_name}':")
        
        with self.pool.connection() as conn:
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
                    schema_details.append(f"Table: {table[0]}")
                    
                    cur.execute(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = %s and table_name = %s
                        ORDER BY ordinal_position;
                        """, 
                        (schema_name, table[0])
                    )
                    
                    details=cur.fetchall()
                    
                    for column, data_type in details:
                        schema_details.append(f"  Column: {column}, Data Type: {data_type}")
                        
                    query=sql.SQL("SELECT COUNT(*) FROM {}.{};").format(
                        sql.Identifier(schema_name),
                        sql.Identifier(table[0])
                    )
                    
                    cur.execute(query)
                    schema_details.append(f" Total Rows: {cur.fetchone()[0]}")
                    
                    if include_sample_data:
                                            
                        sample_query=sql.SQL("SELECT * FROM {}.{} LIMIT 2;").format(
                            sql.Identifier(schema_name),
                            sql.Identifier(table[0])
                        )
                        
                        cur.execute(sample_query)
                        
                        for row in cur.fetchall():
                            schema_details.append(f" Sample Row: {row}")
                    
                    
        return "\n".join(schema_details)
    
    
    
    def execute_sql(self, query: str):

            with self.pool.connection() as conn:
                with conn.cursor() as cur:

                    cur.execute(query)

                    if cur.description:
                        return cur.fetchall()

                    conn.commit()
                    return None