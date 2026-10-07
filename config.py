import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent

DB_HOST=os.getenv("DB_HOST", "localhost")
DB_PORT=int(os.getenv("DB_PORT", "5432"))
DB_NAME=os.getenv("DB_NAME", "postgres")
DB_USER=os.getenv("DB_USER", "postgres")
DB_PASSWORD=os.getenv("DB_PASSWORD", "postgres")
DATABASE_URL=os.getenv("DATABASE_URL",f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

DATABASE_PATH = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "database"))
CSV_PATH = os.getenv("CSV_PATH", str(PROJECT_ROOT / "data"))
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "public")