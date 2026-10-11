from database.connection import db_connection


TABLES_TO_CHECK = [
    "companies",
    "income_statements",
    "balance_sheets",
    "cash_flow_statements",
]


def verify_table_existence():
    """Verify that all expected tables exist in the database."""

    with db_connection.pool.connection() as conn:
        with conn.cursor() as cur:

            for table in TABLES_TO_CHECK:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_name = %s
                    );
                    """,
                    (table,),
                )
                row = cur.fetchone()
                exists = row["exists"]

                if not exists:
                    raise Exception(f"Table '{table}' does not exist in the database.")

    print(f"All {len(TABLES_TO_CHECK)} tables verified.")


def main():

    db_connection.init_db()

    try:
        db_connection.create_tables()
        verify_table_existence()
        print("Database schema initialised successfully.")

    finally:
        db_connection.close_db()


if __name__ == "__main__":
    main()