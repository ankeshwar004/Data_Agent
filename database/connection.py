from psycopg_pool import ConnectionPool

from psycopg.rows import dict_row

import config
import os


class DatabaseConnection:
    def __init__(self, min_size=1, max_size=10):
        self.pool = ConnectionPool(
            conninfo=config.DATABASE_URL,
            min_size=min_size,
            max_size=max_size,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    def init_db(self):
        self.pool.open()

    def close_db(self):
        self.pool.close()

    def create_tables(self):
        schema_path = os.path.join(config.DATABASE_PATH, "schema.sql")

        with open(schema_path, "r") as schema_file:
            schema = schema_file.read()

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema)
                conn.commit()

    def check_pool(self):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone()


db_connection = DatabaseConnection()
