from database.connection import db_connection


def get_schema_details(schema_name: str)-> list | None:
    with db_connection.pool.connection() as conn:
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
            return cur.fetchall()
        
        
        
def execute_query(query: str, params=None)-> list | None:
    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:  
                return cur.fetchall()
            
            conn.commit()
            return None