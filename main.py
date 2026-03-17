import math
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for

import subscription

app = Flask(__name__, template_folder="templates")

ALLOWED_CURRENCIES = {"TWD", "USD", "EUR", "JPY"}
ALLOWED_BILLING_CYCLES = {"monthly", "yearly"}
SORTABLE_COLUMNS = {
    "service_name": "service_name",
    "plan_name": "plan_name",
    "price": "price",
    "billing_cycle": "billing_cycle",
    "next_billing_date": "display_next_billing_date",
    "display_converted": "display_converted",
}


def parse_subscription_form(form):
    service_name = form.get("service_name", "").strip()
    plan_name = form.get("plan_name", "").strip() or None
    currency = form.get("currency", "").strip()
    billing_cycle = form.get("billing_cycle", "").strip()
    next_billing_date = form.get("next_billing_date", "").strip()

    if not service_name:
        raise ValueError("Service name is required.")

    try:
        price = float(form.get("price", "0"))
    except ValueError as exc:
        raise ValueError("Price must be a valid number.") from exc

    if price < 0:
        raise ValueError("Price must be zero or greater.")

    if currency not in ALLOWED_CURRENCIES:
        raise ValueError("Currency is not supported.")

    if billing_cycle not in ALLOWED_BILLING_CYCLES:
        raise ValueError("Billing cycle is not supported.")

    try:
        datetime.strptime(next_billing_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Next billing date must use YYYY-MM-DD.") from exc

    return {
        "service_name": service_name,
        "plan_name": plan_name,
        "price": price,
        "currency": currency,
        "billing_cycle": billing_cycle,
        "next_billing_date": next_billing_date,
    }


def build_form_context(form=None, error_message=None, subscription_data=None):
    source = subscription_data or {}
    form = form or {}
    values = {
        "service_name": form.get("service_name", source.get("service_name", "")),
        "plan_name": form.get("plan_name", source.get("plan_name", "") or ""),
        "price": form.get("price", source.get("price", "")),
        "currency": form.get("currency", source.get("currency", "TWD")),
        "billing_cycle": form.get(
            "billing_cycle", source.get("billing_cycle", "monthly")
        ),
        "next_billing_date": form.get(
            "next_billing_date", source.get("next_billing_date", "")
        ),
    }
    return {"form_values": values, "error_message": error_message}


def sort_subscriptions(subscriptions, sort_key, sort_dir):
    resolved_key = SORTABLE_COLUMNS.get(sort_key, "next_billing_date")
    reverse = sort_dir == "desc"

    def value_for(sub):
        value = sub.get(resolved_key)
        if value is None:
            return ""
        if isinstance(value, str):
            return value.lower()
        return value

    subscriptions.sort(key=value_for, reverse=reverse)
    return resolved_key, "desc" if reverse else "asc"


@app.route("/")
def index():
    subs = subscription.get_subscriptions()
    rates = subscription.get_exchange_rates()
    today = datetime.now().date()
    sort_key = request.args.get("sort", "next_billing_date")
    sort_dir = request.args.get("dir", "asc")

    for sub in subs:
        sub["converted_price"] = sub["price"] / rates.get(sub["currency"], 1.0)
        sub["display_converted"] = math.ceil(sub["converted_price"])
        next_billing_date = subscription.calculate_next_billing_date(sub, today=today)
        if next_billing_date:
            sub["display_next_billing_date"] = next_billing_date.isoformat()
            sub["days_until_due"] = (next_billing_date - today).days
        else:
            sub["display_next_billing_date"] = "Invalid date"
            sub["days_until_due"] = None

    active_sort, active_dir = sort_subscriptions(subs, sort_key, sort_dir)
    total_twd = subscription.calculate_monthly_total(rates=rates)
    due_twd = subscription.calculate_current_month_due(rates=rates, today=today)
    total_usd = total_twd * rates.get("USD", 0.032)
    due_usd = due_twd * rates.get("USD", 0.032)

    display_total_twd = math.ceil(total_twd)
    display_due_twd = math.ceil(due_twd)
    return render_template(
        "index.html",
        subscriptions=subs,
        subscription_count=len(subs),
        active_sort=active_sort,
        active_dir=active_dir,
        display_total_twd=display_total_twd,
        total_usd=total_usd,
        display_due_twd=display_due_twd,
        due_usd=due_usd,
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        try:
            payload = parse_subscription_form(request.form)
        except ValueError as exc:
            context = build_form_context(request.form, error_message=str(exc))
            return render_template("add.html", **context), 400

        subscription.create_subscription(**payload)
        return redirect(url_for("index"))

    return render_template("add.html", **build_form_context())


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    sub = subscription.get_subscription(id)
    if not sub:
        return "Subscription not found", 404

    if request.method == "POST":
        try:
            payload = parse_subscription_form(request.form)
        except ValueError as exc:
            context = build_form_context(
                request.form, error_message=str(exc), subscription_data=sub
            )
            return render_template("edit.html", subscription=sub, **context), 400

        subscription.update_subscription(id, **payload)
        return redirect(url_for("index"))

    return render_template(
        "edit.html", subscription=sub, **build_form_context(subscription_data=sub)
    )


@app.post("/delete/<int:id>")
def delete(id):
    subscription.delete_subscription(id)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
