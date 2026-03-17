import argparse
import sqlite3

from config import get_database_path

SUBSCRIPTION_DB_PATH = get_database_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    service_name TEXT NOT NULL,
    plan_name TEXT,

    price REAL NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('TWD', 'USD', 'EUR', 'JPY')),

    billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('monthly', 'yearly')),
    next_billing_date TEXT NOT NULL
);
"""


def init_db(reset=False):
    SUBSCRIPTION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SUBSCRIPTION_DB_PATH)
    if reset:
        conn.execute("DROP TABLE IF EXISTS subscriptions")
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the MySubs database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the subscriptions table before recreating it.",
    )
    args = parser.parse_args()
    init_db(reset=args.reset)
