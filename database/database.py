from database.connection import DatabaseConnection
from psycopg import sql
from psycopg.errors import QueryCanceled
from typing import Tuple
import logging
import re


logger = logging.getLogger(__name__)



class DatabaseUtils:

    # Process-level cache for structural schema metadata (tables, columns, types).
  
    _schema_cache = {}

    def __init__(self, connection: DatabaseConnection):
        self.connection = connection

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_structural_metadata(self, schema_name: str) -> list[dict]:
        """
        Query information_schema once to collect table names, column names,
        and data types.  Returns a list of table dicts:
            [{"table_name": ..., "columns": [{"column_name": ..., "data_type": ...}, ...]}, ...]
        """
        tables_meta: list[dict] = []

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
                tables = cur.fetchall()

                for table in tables:
                    table_name = table["table_name"]
                    cur.execute(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position;
                        """,
                        (schema_name, table_name),
                    )
                    columns = cur.fetchall()
                    tables_meta.append(
                        {"table_name": table_name, "columns": columns}
                    )

        return tables_meta


    def _get_structural_metadata(self, schema_name: str) -> list[dict]:
        """Return cached structural metadata, fetching it on the first call."""
        
        if schema_name not in DatabaseUtils._schema_cache:
            logger.info("Caching structural schema metadata for '%s'.", schema_name)
            
            DatabaseUtils._schema_cache[schema_name] = self._load_structural_metadata(schema_name)
        return DatabaseUtils._schema_cache[schema_name]
 
 
 
    def schema_details(self, schema_name: str, include_sample_data: bool = True) -> str:
        """
        Retrieves the schema details for the specified schema name.
        Structural metadata (table names, column names, data types) is cached per process so it is only queried once. 
        Row counts and  sample rows are fetched only when *include_sample_data* is True.
        """

        tables_meta = self._get_structural_metadata(schema_name)

        output= [f"Database Schema Details for '{schema_name}':"]

        with self.connection.pool.connection() as conn:
            with conn.cursor() as cur:
                for table_info in tables_meta:
                    table_name = table_info["table_name"]
                    output.append(f"Table: {table_name}")

                    for col in table_info["columns"]:
                        output.append(f"  Column: {col['column_name']}, Data Type: {col['data_type']}")

                    if include_sample_data:
                        count_query = sql.SQL("SELECT COUNT(*) FROM {}.{};").format(
                            sql.Identifier(schema_name),
                            sql.Identifier(table_name),
                        )
                        cur.execute(count_query)
                        output.append(f" Total Rows: {cur.fetchone()['count']}")

                        sample_query = sql.SQL(
                            "SELECT * FROM {}.{} LIMIT 2;"
                        ).format(
                            sql.Identifier(schema_name),
                            sql.Identifier(table_name),
                        )
                        cur.execute(sample_query)
                        for row in cur.fetchall():
                            output.append(f" Sample Row: {row}")

        return "\n".join(output)
    
    
    
    def execute_sql_query(self, query: str)-> tuple[bool, list[dict] | str ]:
        """
        Executes the provided SQL query if it is a valid read-only query and returns the result.
        """
        normalized = query.strip()
        logger.info("Running SQL query.")
        try:
            if ";" in normalized.rstrip(";"):
                raise ValueError("Multiple SQL statements are not permitted.")
            
            with self.connection.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    
                    cur.execute("SELECT set_config('statement_timeout', %s, true)",("5000ms",))  # Set a 5-second timeout for the query execution

                    cur.execute(query)

                    if cur.description:           # if the query returns rows (e.g., SELECT), fetch and return them
                        result = cur.fetchmany(200)
                        if cur.fetchone() is not None:
                            logger.warning("SQL query result truncated to 200 rows.")
                        logger.info("SQL query completed successfully.")
                        return True, result

                    logger.info("SQL query completed with no returned rows.")
                    return True , "No data returned from the query."  

        except QueryCanceled as e:
            logger.warning("SQL query canceled due to timeout.")
            return False , "Query canceled due to timeout."
        
        except Exception as e:
            logger.error("Error executing SQL query: %s", e)
            return False , str(e)
        

      