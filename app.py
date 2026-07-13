import math
import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.security import check_password_hash

from database.db import (
    get_db,
    init_db,
    seed_db,
    create_user,
    create_expense,
    get_user_by_email,
    get_expense_by_id,
    update_expense,
    EXPENSE_CATEGORIES,
)
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

with app.app_context():
    init_db()
    seed_db()


@app.template_filter("inr")
def format_inr(value):
    return "₹{:,.2f}".format(value or 0)


@app.template_filter("friendly_date")
def format_friendly_date(value):
    return datetime.strptime(value.split(" ")[0], "%Y-%m-%d").strftime("%d %b %Y")


@app.template_filter("initials")
def format_initials(name):
    parts = name.split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped_view


def _parse_date_range(start_raw, end_raw):
    if not start_raw or not end_raw:
        return None, None, None

    try:
        start_dt = datetime.strptime(start_raw, "%Y-%m-%d")
        end_dt = datetime.strptime(end_raw, "%Y-%m-%d")
    except ValueError:
        return None, None, None

    if start_dt > end_dt:
        return None, None, "Start date must be before end date. Showing all-time data instead."

    return start_raw, end_raw, None


def _parse_amount(raw):
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return None, "Please enter a valid amount."
    if not math.isfinite(amount) or amount <= 0:
        return None, "Amount must be greater than zero."
    return amount, None


def _parse_expense_date(raw):
    if not raw:
        return None, "Please enter a valid date."
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None, "Please enter a valid date."
    return raw, None


def _render_add_expense_form(error=None, form_values=None):
    return render_template(
        "add_expense.html",
        categories=EXPENSE_CATEGORIES,
        today=datetime.now().strftime("%Y-%m-%d"),
        error=error,
        form=form_values,
    )


def _render_edit_expense_form(expense, error=None, form_values=None):
    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=EXPENSE_CATEGORIES,
        error=error,
        form=form_values,
    )


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")
    if len(password) < 8:
        return render_template(
            "register.html", error="Password must be at least 8 characters."
        )
    if "@" not in email:
        return render_template(
            "register.html", error="Please enter a valid email address."
        )

    user_id = create_user(name, email, password)
    if user_id is None:
        return render_template(
            "register.html", error="An account with that email already exists."
        )

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Invalid email or password.")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/profile")
@login_required
def profile():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))
    start_date, end_date, filter_error = _parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )

    summary = get_summary_stats(user_id, start_date=start_date, end_date=end_date)
    transactions = get_recent_transactions(
        user_id, start_date=start_date, end_date=end_date
    )
    categories = get_category_breakdown(
        user_id, start_date=start_date, end_date=end_date
    )
    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        transactions=transactions,
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        filter_error=filter_error,
    )


@app.route("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "GET":
        return _render_add_expense_form()

    amount_raw = request.form.get("amount", "")
    category = request.form.get("category", "")
    date_raw = request.form.get("date", "")
    description_raw = request.form.get("description", "").strip()
    description = description_raw or None

    form_values = {
        "amount": amount_raw,
        "category": category,
        "date": date_raw,
        "description": description_raw,
    }

    amount, error = _parse_amount(amount_raw)
    if error:
        return _render_add_expense_form(error, form_values)

    if category not in EXPENSE_CATEGORIES:
        return _render_add_expense_form("Please choose a valid category.", form_values)

    date_value, error = _parse_expense_date(date_raw)
    if error:
        return _render_add_expense_form(error, form_values)

    create_expense(session["user_id"], amount, category, date_value, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)
    expense = dict(expense)

    if request.method == "GET":
        return _render_edit_expense_form(expense)

    amount_raw = request.form.get("amount", "")
    category = request.form.get("category", "")
    date_raw = request.form.get("date", "")
    description_raw = request.form.get("description", "").strip()
    description = description_raw or None

    form_values = {
        "amount": amount_raw,
        "category": category,
        "date": date_raw,
        "description": description_raw,
    }

    amount, error = _parse_amount(amount_raw)
    if error:
        return _render_edit_expense_form(expense, error, form_values)

    if category not in EXPENSE_CATEGORIES:
        return _render_edit_expense_form(expense, "Please choose a valid category.", form_values)

    date_value, error = _parse_expense_date(date_raw)
    if error:
        return _render_edit_expense_form(expense, error, form_values)

    update_expense(id, session["user_id"], amount, category, date_value, description)
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
