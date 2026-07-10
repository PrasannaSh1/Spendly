"""
Tests for Step 6: Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-profile-page.md

These tests exercise `GET /profile` with the optional `start_date` /
`end_date` query-string filter described in the spec. They do not assume
anything about how `app.py` / `database/queries.py` implement the filter
internally -- only the documented, user-observable behavior (status codes,
rendered content, DoD checklist) is asserted.

Fixtures `app`, `client` (via pytest-flask), and `seeded_user` come from
tests/conftest.py, matching the conventions already used in
tests/test_profile.py and tests/test_login_logout.py.
"""

import re

import pytest

import database.db as db


def _insert_expenses(user_id, expenses):
    """expenses: list of (amount, category, date, description) tuples."""
    conn = db.get_db()
    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(user_id, *e) for e in expenses],
    )
    conn.commit()
    conn.close()


def _get_user_id(email):
    conn = db.get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()
    return row["id"]


def _login(client, seeded_user):
    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )


def _sum_category_percentages(body):
    """Extract every `<int>%` occurrence in the rendered page and sum them.

    The category breakdown is the only section on the profile page expected
    to render per-category percentages, so summing all percentage-looking
    tokens on the page is a reasonable proxy for "the category percentages
    sum to 100".
    """
    return sum(int(match) for match in re.findall(r"(\d+)%", body))


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #

class TestProfileFilterAuthGuard:
    @pytest.mark.parametrize(
        "path",
        [
            "/profile",
            "/profile?start_date=2026-06-01&end_date=2026-06-30",
            "/profile?start_date=not-a-date&end_date=2026-06-30",
        ],
    )
    def test_unauthenticated_request_redirects_to_login(self, client, path):
        response = client.get(path)
        assert response.status_code == 302, f"Expected redirect for {path}"
        assert response.headers["Location"] == "/login"


# --------------------------------------------------------------------- #
# No filter params: behavior unchanged                                   #
# --------------------------------------------------------------------- #

class TestProfileNoFilterParams:
    def test_no_query_params_shows_alltime_totals(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (100.0, "Food", "2026-06-15", "June expense"),
            (500.0, "Bills", "2026-07-01", "July expense"),
        ])
        _login(client, seeded_user)

        response = client.get("/profile")
        body = response.data.decode()

        assert response.status_code == 200
        assert "June expense" in body
        assert "July expense" in body
        assert "600.00" in body  # 100 + 500, all-time total
        assert ">2<" in body  # transaction count

    def test_no_query_params_does_not_show_clear_filter(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile")
        assert "Clear filter" not in response.data.decode()

    def test_no_query_params_no_fallback_message(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile")
        assert response.status_code == 200
        assert "before end date" not in response.data.decode()


# --------------------------------------------------------------------- #
# Valid range filters all three sections                                 #
# --------------------------------------------------------------------- #

class TestProfileValidRangeFilter:
    def test_valid_range_filters_summary_transactions_and_categories(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (100.0, "Food", "2026-06-15", "June expense"),
            (500.0, "Bills", "2026-07-01", "July expense"),
        ])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        body = response.data.decode()

        assert response.status_code == 200
        assert "June expense" in body
        assert "July expense" not in body
        assert "100.00" in body
        assert "Food" in body
        assert "Bills" not in body

    def test_valid_range_recomputes_total_and_count_correctly(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (100.0, "Food", "2026-06-05", "In range 1"),
            (250.0, "Transport", "2026-06-20", "In range 2"),
            (900.0, "Bills", "2026-07-15", "Out of range"),
        ])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        body = response.data.decode()

        assert response.status_code == 200
        assert "350.00" in body  # 100 + 250, filtered total only
        assert ">2<" in body  # 2 transactions in range
        assert "Out of range" not in body

    def test_valid_range_top_category_reflects_filtered_data_only(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (10.0, "Food", "2026-06-10", "Small June expense"),
            (5000.0, "Shopping", "2026-07-05", "Huge July expense"),
        ])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        body = response.data.decode()

        # Top category within the filtered range should be Food, not the
        # much larger all-time Shopping expense that falls outside the range.
        assert "Top category" in body
        assert "Food" in body
        assert "Shopping" not in body
        assert "Huge July expense" not in body

    def test_valid_range_shows_clear_filter_link(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-06-15", "June expense")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        assert "Clear filter" in response.data.decode()


# --------------------------------------------------------------------- #
# Category percentages sum to 100 under a filtered range                 #
# --------------------------------------------------------------------- #

class TestCategoryPercentagesFiltered:
    def test_percentages_sum_to_100_for_filtered_range(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (33.34, "Food", "2026-06-05", "Food in range"),
            (33.33, "Transport", "2026-06-10", "Transport in range"),
            (33.33, "Bills", "2026-06-20", "Bills in range"),
            (999.0, "Shopping", "2026-07-01", "Out of range, must not affect pct"),
        ])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        body = response.data.decode()

        assert response.status_code == 200
        assert _sum_category_percentages(body) == 100, (
            "Category breakdown percentages must sum to 100 for a filtered range"
        )

    def test_percentages_sum_to_100_for_single_category_in_range(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(50.0, "Food", "2026-06-15", "Only expense in range")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        body = response.data.decode()

        assert _sum_category_percentages(body) == 100


# --------------------------------------------------------------------- #
# Bookmarkable filter form                                                #
# --------------------------------------------------------------------- #

class TestFilterFormBookmarkable:
    def test_filter_form_uses_get_method(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile")
        assert 'method="get"' in response.data.decode().lower()

    def test_filter_form_has_start_and_end_date_inputs(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile")
        body = response.data.decode()
        assert 'name="start_date"' in body
        assert 'name="end_date"' in body

    def test_submitted_dates_reflected_back_into_form_values(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-06-15", "June expense")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        body = response.data.decode()

        assert 'value="2026-06-01"' in body
        assert 'value="2026-06-30"' in body


# --------------------------------------------------------------------- #
# Clear filter link visibility                                           #
# --------------------------------------------------------------------- #

class TestClearFilterLink:
    def test_clear_filter_absent_when_no_filter_applied(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile")
        assert "Clear filter" not in response.data.decode()

    def test_clear_filter_present_when_valid_filter_applied(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        assert "Clear filter" in response.data.decode()

    def test_clear_filter_links_back_to_unfiltered_profile(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        body = response.data.decode()
        assert 'href="/profile"' in body

    def test_following_clear_filter_link_returns_alltime_data(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (100.0, "Food", "2026-06-15", "June expense"),
            (500.0, "Bills", "2026-07-01", "July expense"),
        ])
        _login(client, seeded_user)

        client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        response = client.get("/profile")  # simulate clicking "Clear filter"
        body = response.data.decode()

        assert "June expense" in body
        assert "July expense" in body
        assert "Clear filter" not in body


# --------------------------------------------------------------------- #
# start_date after end_date: friendly fallback, no error                 #
# --------------------------------------------------------------------- #

class TestInvalidRangeFallback:
    def test_start_after_end_does_not_error(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=2026-07-01&end_date=2026-06-01")
        assert response.status_code == 200

    def test_start_after_end_falls_back_to_alltime_data(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (100.0, "Food", "2026-06-15", "Should still show"),
            (200.0, "Bills", "2026-07-20", "Also still show"),
        ])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-07-01&end_date=2026-06-01")
        body = response.data.decode()

        assert "Should still show" in body
        assert "Also still show" in body
        assert "300.00" in body  # all-time total, filter ignored

    def test_start_after_end_shows_friendly_message(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=2026-07-01&end_date=2026-06-01")
        body = response.data.decode()
        assert "before end date" in body, "Expected a friendly inline message about the invalid range"

    def test_start_after_end_does_not_show_clear_filter(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=2026-07-01&end_date=2026-06-01")
        assert "Clear filter" not in response.data.decode()


# --------------------------------------------------------------------- #
# Malformed dates: treated as absent, no error, no message               #
# --------------------------------------------------------------------- #

class TestMalformedDatesTreatedAsAbsent:
    @pytest.mark.parametrize(
        "start_date,end_date",
        [
            ("not-a-date", "2026-06-30"),
            ("2026-06-01", "not-a-date"),
            ("2026/06/01", "2026/06/30"),
            ("06-01-2026", "06-30-2026"),
            ("", "2026-06-30"),
            ("2026-06-01", ""),
            ("2026-13-40", "2026-06-30"),
        ],
    )
    def test_malformed_dates_do_not_error(self, client, seeded_user, start_date, end_date):
        _login(client, seeded_user)
        response = client.get(f"/profile?start_date={start_date}&end_date={end_date}")
        assert response.status_code == 200, f"Malformed input {start_date!r}/{end_date!r} must not 500"

    def test_malformed_dates_fall_back_to_alltime_data(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-06-15", "Still shown")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=not-a-date&end_date=2026-06-30")
        body = response.data.decode()

        assert "Still shown" in body

    def test_malformed_dates_show_no_error_message(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=not-a-date&end_date=2026-06-30")
        body = response.data.decode()
        assert "before end date" not in body

    def test_malformed_dates_do_not_show_clear_filter(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=not-a-date&end_date=2026-06-30")
        assert "Clear filter" not in response.data.decode()


# --------------------------------------------------------------------- #
# start_date == end_date: valid single-day filter                        #
# --------------------------------------------------------------------- #

class TestSingleDayFilter:
    def test_equal_start_and_end_date_is_not_an_error(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=2026-06-15&end_date=2026-06-15")
        assert response.status_code == 200

    def test_equal_start_and_end_date_filters_to_that_single_day(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [
            (100.0, "Food", "2026-06-14", "Day before"),
            (200.0, "Transport", "2026-06-15", "The day itself"),
            (300.0, "Bills", "2026-06-16", "Day after"),
        ])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-15&end_date=2026-06-15")
        body = response.data.decode()

        assert "The day itself" in body
        assert "Day before" not in body
        assert "Day after" not in body
        assert "200.00" in body
        assert ">1<" in body

    def test_equal_start_and_end_date_shows_clear_filter(self, client, seeded_user):
        _login(client, seeded_user)
        response = client.get("/profile?start_date=2026-06-15&end_date=2026-06-15")
        assert "Clear filter" in response.data.decode()


# --------------------------------------------------------------------- #
# Valid range with zero matching expenses                                #
# --------------------------------------------------------------------- #

class TestFilteredZeroMatches:
    def test_zero_matches_returns_200_without_exception(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-07-01", "Out of range")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
        assert response.status_code == 200

    def test_zero_matches_shows_existing_empty_state(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-07-01", "Out of range")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
        body = response.data.decode()

        assert "No expenses yet" in body
        assert "No category data yet" in body
        assert "₹0.00" in body
        assert "—" in body  # top category placeholder

    def test_zero_matches_still_shows_clear_filter_since_filter_is_active(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-07-01", "Out of range")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
        assert "Clear filter" in response.data.decode()


# --------------------------------------------------------------------- #
# ₹ currency formatting in filtered view                                 #
# --------------------------------------------------------------------- #

class TestFilteredViewCurrencyFormatting:
    def test_filtered_view_with_results_shows_rupee_symbol(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-06-15", "June expense")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        assert "₹".encode() in response.data

    def test_filtered_view_with_zero_matches_shows_rupee_symbol(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-07-01", "Out of range")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
        assert "₹0.00".encode() in response.data

    def test_no_amount_displayed_with_bare_dollar_sign(self, client, seeded_user):
        user_id = _get_user_id(seeded_user["email"])
        _insert_expenses(user_id, [(100.0, "Food", "2026-06-15", "June expense")])
        _login(client, seeded_user)

        response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
        assert b"$100.00" not in response.data
