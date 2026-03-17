import math
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for

import subscription
from config import get_secret_key

app = Flask(__name__, template_folder="templates")
app.secret_key = get_secret_key()

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
DEFAULT_SORT_KEY = "service_name"
DEFAULT_SORT_DIR = "asc"


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


def get_current_sorting():
    requested_sort = request.args.get("sort")
    requested_dir = request.args.get("dir")

    if requested_sort in SORTABLE_COLUMNS:
        sort_key = requested_sort
        sort_dir = "desc" if requested_dir == "desc" else "asc"
    else:
        sort_key = session.get("sort_key", DEFAULT_SORT_KEY)
        if sort_key not in SORTABLE_COLUMNS:
            sort_key = DEFAULT_SORT_KEY

        stored_dir = session.get("sort_dir", DEFAULT_SORT_DIR)
        sort_dir = "desc" if stored_dir == "desc" else "asc"

    session["sort_key"] = sort_key
    session["sort_dir"] = sort_dir
    return sort_key, sort_dir


def get_sort_params():
    sort_key = session.get("sort_key", DEFAULT_SORT_KEY)
    if sort_key not in SORTABLE_COLUMNS:
        sort_key = DEFAULT_SORT_KEY

    sort_dir = session.get("sort_dir", DEFAULT_SORT_DIR)
    if sort_dir not in {"asc", "desc"}:
        sort_dir = DEFAULT_SORT_DIR

    return {"sort": sort_key, "dir": sort_dir}


def redirect_to_index():
    sort_params = get_sort_params()
    return redirect(url_for("index", sort=sort_params["sort"], dir=sort_params["dir"]))


def sort_subscriptions(subscriptions, sort_key, sort_dir):
    resolved_key = SORTABLE_COLUMNS.get(sort_key, SORTABLE_COLUMNS[DEFAULT_SORT_KEY])
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
    sort_key, sort_dir = get_current_sorting()

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
        sort_params=get_sort_params(),
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
            context["sort_params"] = get_sort_params()
            return render_template("add.html", **context), 400

        subscription.create_subscription(**payload)
        return redirect_to_index()

    context = build_form_context()
    context["sort_params"] = get_sort_params()
    return render_template("add.html", **context)


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
            context["sort_params"] = get_sort_params()
            return render_template("edit.html", subscription=sub, **context), 400

        subscription.update_subscription(id, **payload)
        return redirect_to_index()

    context = build_form_context(subscription_data=sub)
    context["sort_params"] = get_sort_params()
    return render_template("edit.html", subscription=sub, **context)


@app.post("/delete/<int:id>")
def delete(id):
    subscription.delete_subscription(id)
    return redirect_to_index()


if __name__ == "__main__":
    app.run(debug=True)
