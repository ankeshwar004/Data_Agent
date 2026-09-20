from psycopg_pool import ConnectionPool

from psycopg.rows import dict_row

import config
import os

DATABASE_URL=config.DATABASE_URL


pool=ConnectionPool(conninfo=DATABASE_URL,min_size=1,max_size=10,open=False,kwargs={"row_factory": dict_row})


def init_db():
    pool.open()


def close_db():
    pool.close()
    
def create_tables():
    schema_path=os.path.join(config.DATABASE_PATH, "schema.sql")
    
    with open(schema_path, "r") as f:
        schema=f.read()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
            conn.commit()


def check_pool():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            result=cur.fetchone()
            return result