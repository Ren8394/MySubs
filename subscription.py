import sqlite3
from datetime import datetime
from time import time

import requests

from config import get_database_path

SUBSCRIPTION_DB_PATH = get_database_path()
EXCHANGE_RATE_CACHE_TTL_SECONDS = 1800
FALLBACK_RATES = {"TWD": 1.0, "USD": 0.032, "EUR": 0.029, "JPY": 4.5}
_exchange_rate_cache = {}


def get_conn():
    SUBSCRIPTION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SUBSCRIPTION_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_exchange_rates(base="TWD"):
    cached = _exchange_rate_cache.get(base)
    now = time()
    if cached and now - cached["timestamp"] < EXCHANGE_RATE_CACHE_TTL_SECONDS:
        return cached["rates"]

    try:
        response = requests.get(
            f"https://api.exchangerate-api.com/v4/latest/{base}", timeout=1.5
        )
        response.raise_for_status()
        data = response.json()
        rates = data["rates"]
        _exchange_rate_cache[base] = {"timestamp": now, "rates": rates}
        return rates
    except requests.RequestException:
        if cached:
            return cached["rates"]
        return FALLBACK_RATES


# CRUD Operations
###############################
def create_subscription(
    service_name, plan_name, price, currency, billing_cycle, next_billing_date
):
    """Create a new subscription."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO subscriptions (service_name, plan_name, price, currency, billing_cycle, next_billing_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (service_name, plan_name, price, currency, billing_cycle, next_billing_date),
    )
    conn.commit()
    subscription_id = cursor.lastrowid
    conn.close()
    return subscription_id


def get_subscriptions():
    """Get all subscriptions."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_subscription(subscription_id):
    """Get a subscription by ID."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def update_subscription(subscription_id, **kwargs):
    """Update a subscription."""
    allowed_fields = [
        "service_name",
        "plan_name",
        "price",
        "currency",
        "billing_cycle",
        "next_billing_date",
    ]
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [subscription_id]
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE subscriptions SET {set_clause} WHERE id = ?", values)
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def delete_subscription(subscription_id):
    """Delete a subscription by ID."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


# Utility Functions
###############################
def calculate_monthly_total(rates=None):
    """Calculate the total monthly cost of all subscriptions in TWD."""
    subscriptions = get_subscriptions()
    if not subscriptions:
        return 0.0

    rates = rates or get_exchange_rates()
    twd_total = 0.0
    for sub in subscriptions:
        price_in_twd = sub["price"] / rates.get(sub["currency"], 1.0)
        if sub["billing_cycle"] == "monthly":
            twd_total += price_in_twd
        elif sub["billing_cycle"] == "yearly":
            twd_total += price_in_twd / 12
        else:
            twd_total += 0.0
    return twd_total


def calculate_current_month_due(rates=None):
    """Calculate the total due for the current month in TWD."""
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    subscriptions = get_subscriptions()
    rates = rates or get_exchange_rates()
    twd_due = 0.0
    for sub in subscriptions:
        try:
            next_date = datetime.strptime(sub["next_billing_date"], "%Y-%m-%d")
            if next_date.year == current_year and next_date.month == current_month:
                price_in_twd = sub["price"] / rates.get(sub["currency"], 1.0)
                twd_due += price_in_twd
        except ValueError:
            # Invalid date format, skip
            continue
    return twd_due
