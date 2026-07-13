"""
Tests for Step 7: Add Expense.

Spec: .claude/specs/07-add-expense.md

These tests exercise `GET/POST /expenses/add` purely against the documented,
user-observable behavior in the spec's Routes / Rules for implementation /
Definition of Done sections -- they do not assume anything about how
`app.py` implements validation or how `database/db.py` structures its
helpers internally, beyond the already-existing `expenses` table columns
(`user_id`, `amount`, `category`, `date`, `description`) and the
`create_user()` / `get_db()` conventions already used elsewhere in the
suite.

Fixtures `app`, `client` (via pytest-flask), and `seeded_user` come from
tests/conftest.py, matching the conventions already used in
tests/test_profile.py and tests/test_06-date-filter-profile-page.py.
"""

import datetime

import pytest

import database.db as db


# --------------------------------------------------------------------- #
# Helpers                                                                #
# --------------------------------------------------------------------- #

# The fixed set of known categories, per the spec's Templates section.
KNOWN_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def _get_user_id(email):
    conn = db.get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()
    return row["id"]


def _count_expenses(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            row = conn.execute("SELECT COUNT(*) AS count FROM expenses").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM expenses WHERE user_id = ?",
                (user_id,),
            ).fetchone()
    finally:
        conn.close()
    return row["count"]


def _get_expenses(user_id):
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _login(client, seeded_user):
    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )


def _valid_payload(**overrides):
    payload = {
        "amount": "42.50",
        "category": "Food",
        "date": "2026-07-01",
        "description": "Lunch with friends",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #

class TestAddExpenseAuthGuard:
    def test_get_add_expense_logged_out_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

    def test_post_add_expense_logged_out_redirects_to_login(self, client):
        response = client.post("/expenses/add", data=_valid_payload())
        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

    def test_post_add_expense_logged_out_does_not_create_row(self, client):
        client.post("/expenses/add", data=_valid_payload())
        assert _count_expenses() == 0, "Logged-out POST must not write to the DB"


# --------------------------------------------------------------------- #
# GET renders the form                                                   #
# --------------------------------------------------------------------- #

class TestAddExpenseFormRendering:
    def test_get_add_expense_logged_in_returns_200(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/expenses/add")
        assert response.status_code == 200

    def test_get_add_expense_shows_amount_field(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/expenses/add")
        body = response.data.decode()
        assert 'name="amount"' in body
        assert 'type="number"' in body

    def test_get_add_expense_shows_category_field_with_known_categories(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/expenses/add")
        body = response.data.decode()
        assert 'name="category"' in body
        for category in KNOWN_CATEGORIES:
            assert category in body, f"Expected category option {category!r} in the form"

    def test_get_add_expense_shows_date_field_defaulted_to_today(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/expenses/add")
        body = response.data.decode()
        today = datetime.date.today().isoformat()
        assert 'name="date"' in body
        assert today in body, "Date field should default to today's date"

    def test_get_add_expense_shows_description_field(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/expenses/add")
        body = response.data.decode()
        assert 'name="description"' in body

    def test_get_add_expense_form_posts_to_add_expense_route(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/expenses/add")
        body = response.data.decode()
        assert 'action="/expenses/add"' in body

    def test_get_add_expense_has_cancel_link_back_to_profile(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/expenses/add")
        body = response.data.decode()
        assert 'href="/profile"' in body


# --------------------------------------------------------------------- #
# Valid submission                                                       #
# --------------------------------------------------------------------- #

class TestAddExpenseValidSubmission:
    def test_valid_post_redirects_to_profile(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.post("/expenses/add", data=_valid_payload())
        assert response.status_code == 302
        assert response.headers["Location"] == "/profile"

    def test_valid_post_creates_expense_row(self, client, seeded_user):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])
        assert _count_expenses(user_id) == 0

        client.post("/expenses/add", data=_valid_payload())

        assert _count_expenses(user_id) == 1

    def test_valid_post_stores_submitted_field_values(self, client, seeded_user):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        client.post(
            "/expenses/add",
            data=_valid_payload(
                amount="123.45", category="Transport", date="2026-05-20",
                description="Cab ride",
            ),
        )

        rows = _get_expenses(user_id)
        assert len(rows) == 1
        assert rows[0]["amount"] == 123.45
        assert rows[0]["category"] == "Transport"
        assert rows[0]["date"] == "2026-05-20"
        assert rows[0]["description"] == "Cab ride"

    def test_valid_post_scopes_expense_to_session_user(self, client, seeded_user):
        # A second, unrelated user exists in the DB.
        db.create_user("Other User", "other@example.com", "other-password")
        other_user_id = _get_user_id("other@example.com")

        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        client.post("/expenses/add", data=_valid_payload())

        assert _count_expenses(user_id) == 1
        assert _count_expenses(other_user_id) == 0, (
            "Expense must be scoped to the logged-in user, not any other account"
        )

    def test_post_ignores_user_id_supplied_in_form_and_uses_session_user(self, client, seeded_user):
        db.create_user("Other User", "other@example.com", "other-password")
        other_user_id = _get_user_id("other@example.com")

        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        # Attempt to spoof ownership via a crafted form field.
        client.post("/expenses/add", data=_valid_payload(user_id=str(other_user_id)))

        assert _count_expenses(user_id) == 1
        assert _count_expenses(other_user_id) == 0, (
            "user_id must always come from session, never from form input"
        )

    def test_valid_post_increases_transaction_count_for_user(self, client, seeded_user):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        before = _count_expenses(user_id)
        client.post("/expenses/add", data=_valid_payload(amount="10", date="2026-07-02"))
        client.post("/expenses/add", data=_valid_payload(amount="20", date="2026-07-03"))
        after = _count_expenses(user_id)

        assert after == before + 2

    def test_valid_post_without_description_key_still_creates_row(self, client, seeded_user):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        payload = _valid_payload()
        del payload["description"]

        response = client.post("/expenses/add", data=payload)

        assert response.status_code == 302
        assert response.headers["Location"] == "/profile"
        assert _count_expenses(user_id) == 1

    def test_valid_post_with_empty_description_still_creates_row(self, client, seeded_user):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        response = client.post("/expenses/add", data=_valid_payload(description=""))

        assert response.status_code == 302
        assert _count_expenses(user_id) == 1


# --------------------------------------------------------------------- #
# Amount validation                                                      #
# --------------------------------------------------------------------- #

class TestAddExpenseAmountValidation:
    @pytest.mark.parametrize(
        "bad_amount",
        ["0", "-5", "-0.01", "abc", "", "12abc", "NaN"],
    )
    def test_invalid_amount_does_not_create_row(self, client, seeded_user, bad_amount):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        response = client.post("/expenses/add", data=_valid_payload(amount=bad_amount))

        assert response.status_code == 200, (
            f"Invalid amount {bad_amount!r} must re-render the form, not redirect"
        )
        assert _count_expenses(user_id) == 0, (
            f"Invalid amount {bad_amount!r} must not create a DB row"
        )

    @pytest.mark.parametrize(
        "bad_amount",
        ["0", "-5", "abc"],
    )
    def test_invalid_amount_does_not_raise_500(self, client, seeded_user, bad_amount):
        _login(client, seeded_user)
        response = client.post("/expenses/add", data=_valid_payload(amount=bad_amount))
        assert response.status_code != 500

    def test_invalid_amount_shows_inline_error(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.post("/expenses/add", data=_valid_payload(amount="-10"))
        body = response.data.decode()
        assert response.status_code == 200
        assert "error" in body.lower(), "Expected an inline error indicator in the response"

    def test_invalid_amount_preserves_other_submitted_values(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.post(
            "/expenses/add",
            data=_valid_payload(amount="-10", category="Health", date="2026-05-15",
                                 description="Preserve me"),
        )
        body = response.data.decode()
        assert "Preserve me" in body
        assert "2026-05-15" in body


# --------------------------------------------------------------------- #
# Category validation                                                    #
# --------------------------------------------------------------------- #

class TestAddExpenseCategoryValidation:
    @pytest.mark.parametrize(
        "bad_category",
        ["NotACategory", "food", "", "<script>alert(1)</script>"],
    )
    def test_invalid_category_does_not_create_row(self, client, seeded_user, bad_category):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        response = client.post("/expenses/add", data=_valid_payload(category=bad_category))

        assert response.status_code == 200, (
            f"Invalid category {bad_category!r} must re-render the form, not redirect"
        )
        assert _count_expenses(user_id) == 0, (
            f"Invalid category {bad_category!r} must not create a DB row"
        )

    def test_invalid_category_does_not_raise_500(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.post("/expenses/add", data=_valid_payload(category="NotACategory"))
        assert response.status_code != 500

    def test_invalid_category_shows_inline_error(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.post("/expenses/add", data=_valid_payload(category="NotACategory"))
        body = response.data.decode()
        assert response.status_code == 200
        assert "error" in body.lower()


# --------------------------------------------------------------------- #
# Date validation                                                        #
# --------------------------------------------------------------------- #

class TestAddExpenseDateValidation:
    @pytest.mark.parametrize(
        "bad_date",
        ["not-a-date", "2026-13-40", "13/07/2026", "", "2026/07/13"],
    )
    def test_invalid_date_does_not_create_row(self, client, seeded_user, bad_date):
        _login(client, seeded_user)
        user_id = _get_user_id(seeded_user["email"])

        response = client.post("/expenses/add", data=_valid_payload(date=bad_date))

        assert response.status_code == 200, (
            f"Invalid date {bad_date!r} must re-render the form, not redirect"
        )
        assert _count_expenses(user_id) == 0, (
            f"Invalid date {bad_date!r} must not create a DB row"
        )

    @pytest.mark.parametrize(
        "bad_date",
        ["not-a-date", "2026-13-40", "13/07/2026"],
    )
    def test_invalid_date_does_not_raise_500(self, client, seeded_user, bad_date):
        _login(client, seeded_user)
        response = client.post("/expenses/add", data=_valid_payload(date=bad_date))
        assert response.status_code != 500

    def test_invalid_date_shows_inline_error(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.post("/expenses/add", data=_valid_payload(date="not-a-date"))
        body = response.data.decode()
        assert response.status_code == 200
        assert "error" in body.lower()
