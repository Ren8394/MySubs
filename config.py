import os
from pathlib import Path


BASE_DIR = Path(__file__).parent
DEFAULT_DB_PATH = BASE_DIR / "mysubs.db"


def get_database_path() -> Path:
    raw_path = os.getenv("MYSUBS_DB_PATH")
    if not raw_path:
        return DEFAULT_DB_PATH

    db_path = Path(raw_path).expanduser()
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    return db_path
