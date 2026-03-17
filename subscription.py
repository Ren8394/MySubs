import sqlite3
from calendar import monthrange
from datetime import date, datetime
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
def parse_billing_date(raw_date):
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None


def build_billing_date(year, month, anchor_day):
    target_day = min(anchor_day, monthrange(year, month)[1])
    return date(year, month, target_day)


def add_months(source_date, months, anchor_day=None):
    target_month_index = source_date.month - 1 + months
    target_year = source_date.year + target_month_index // 12
    target_month = target_month_index % 12 + 1
    target_day = anchor_day or source_date.day
    return build_billing_date(target_year, target_month, target_day)


def calculate_next_billing_date(subscription_record, today=None):
    today = today or date.today()
    base_date = parse_billing_date(subscription_record["next_billing_date"])
    if not base_date:
        return None

    if base_date >= today:
        return base_date

    billing_cycle = subscription_record.get("billing_cycle")
    next_date = base_date
    anchor_day = base_date.day

    if billing_cycle == "monthly":
        while next_date < today:
            next_date = add_months(next_date, 1, anchor_day=anchor_day)
        return next_date

    if billing_cycle == "yearly":
        while next_date < today:
            next_date = add_months(next_date, 12, anchor_day=anchor_day)
        return next_date

    return base_date


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


def calculate_current_month_due(rates=None, today=None):
    """Calculate the total due for the current month in TWD."""
    today = today or date.today()
    now = datetime.combine(today, datetime.min.time())
    current_year = now.year
    current_month = now.month

    subscriptions = get_subscriptions()
    rates = rates or get_exchange_rates()
    twd_due = 0.0
    for sub in subscriptions:
        next_date = calculate_next_billing_date(sub, today=today)
        if not next_date:
            continue
        if next_date.year == current_year and next_date.month == current_month:
            price_in_twd = sub["price"] / rates.get(sub["currency"], 1.0)
            twd_due += price_in_twd
    return twd_due
