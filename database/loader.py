import os
import config
import csv
from psycopg import sql
from database.connection import pool



def get_columns_from_csv(file_path: str)-> list | None:
    """
    Reads the first row of the CSV file to get the column names.
    """
    
    with open(file_path, "r") as f:
        reader = csv.reader(f)
        columns = next(reader)
    
    return columns


def load_csv(table_name: str, csv_file_name: str):
    """
    Loads data from a CSV file into the specified table in the database.
    """
    
    file_path=os.path.join(config.CSV_PATH, csv_file_name)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file '{file_path}' not found.")
    
    columns=get_columns_from_csv(file_path)
    
    copy_sql=sql.SQL("""
                     COPY {} ({}) FROM STDIN WITH (
                         FORMAT CSV,
                         HEADER TRUE,
                         DELIMITER ',',
                         NULL ''
                     )
                    """).format(
                        sql.Identifier(table_name),
                        sql.SQL(', ').join(sql.Identifier(col) for col in columns) if columns else sql.SQL('*')
                         )
                    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            with open(file_path, 'r') as f:
                cur.copy_expert(copy_sql, f)
            conn.commit()
                     
     