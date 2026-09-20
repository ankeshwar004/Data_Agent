from database.connection import pool , init_db, create_tables , close_db
from database.schema import create_tables
from database.loader import load_csv


def verify_table_existence():
    tables_to_check = ["users", "vehicles", "rides", "payments", "ratings"]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            
            for table in tables_to_check:
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
                exists = cur.fetchone()[0]
                
                if not exists:
                    raise Exception(f"Table '{table}' does not exist in the database.")


def main():

    init_db()

    try:
        create_tables()

        verify_table_existence()

        load_csv("users","users.csv")

        load_csv("vehicles","vehicles.csv",)

        load_csv("rides","rides.csv")
        
        load_csv("payments","payments.csv")

        load_csv("ratings","ratings.csv")
        

    finally:
        close_db()


if __name__ == "__main__":
    main()