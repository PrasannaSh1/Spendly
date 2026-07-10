import database.db as db
import database.queries as queries


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


def _user_id(email):
    conn = db.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


# ---------------------------------------------------------------- #
# get_user_by_id
# ---------------------------------------------------------------- #

def test_get_user_by_id_returns_dict_for_existing_user(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    result = queries.get_user_by_id(user_id)

    assert result["name"] == "Test User"
    assert result["email"] == seeded_user["email"]
    parts = result["member_since"].split()
    assert len(parts) == 2
    assert parts[1].isdigit() and len(parts[1]) == 4


def test_get_user_by_id_returns_none_for_missing_user(app):
    assert queries.get_user_by_id(9999) is None


# ---------------------------------------------------------------- #
# get_summary_stats
# ---------------------------------------------------------------- #

def test_get_summary_stats_with_expenses(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [
        (100.0, "Food", "2026-07-01", "Groceries"),
        (300.0, "Bills", "2026-07-02", "Electricity"),
    ])

    result = queries.get_summary_stats(user_id)

    assert result["total_spent"] == 400.0
    assert result["transaction_count"] == 2
    assert result["top_category"] == "Bills"


def test_get_summary_stats_with_no_expenses(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    result = queries.get_summary_stats(user_id)

    assert result == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


def test_get_summary_stats_filtered_by_date_range(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [
        (100.0, "Food", "2026-06-15", "In range"),
        (200.0, "Bills", "2026-06-20", "In range"),
        (300.0, "Transport", "2026-07-01", "Out of range"),
    ])

    result = queries.get_summary_stats(user_id, start_date="2026-06-01", end_date="2026-06-30")

    assert result["total_spent"] == 300.0
    assert result["transaction_count"] == 2
    assert result["top_category"] == "Bills"


def test_get_summary_stats_single_day_filter(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [
        (100.0, "Food", "2026-06-15", "Target day"),
        (200.0, "Bills", "2026-06-16", "Different day"),
    ])

    result = queries.get_summary_stats(user_id, start_date="2026-06-15", end_date="2026-06-15")

    assert result["total_spent"] == 100.0
    assert result["transaction_count"] == 1


def test_get_summary_stats_filter_no_matches_returns_zeroed(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [(100.0, "Food", "2026-07-01", "Out of range")])

    result = queries.get_summary_stats(user_id, start_date="2026-01-01", end_date="2026-01-31")

    assert result == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


# ---------------------------------------------------------------- #
# get_recent_transactions
# ---------------------------------------------------------------- #

def test_get_recent_transactions_newest_first(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [
        (100.0, "Food", "2026-07-02", "Second"),
        (200.0, "Bills", "2026-07-05", "Newest"),
        (300.0, "Transport", "2026-07-01", "Oldest"),
    ])

    result = queries.get_recent_transactions(user_id)

    assert [txn["description"] for txn in result] == ["Newest", "Second", "Oldest"]
    assert set(result[0].keys()) == {"date", "description", "category", "amount"}


def test_get_recent_transactions_empty(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    assert queries.get_recent_transactions(user_id) == []


def test_get_recent_transactions_filtered_by_date_range(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [
        (100.0, "Food", "2026-06-15", "In range"),
        (200.0, "Bills", "2026-07-01", "Out of range"),
    ])

    result = queries.get_recent_transactions(user_id, start_date="2026-06-01", end_date="2026-06-30")

    assert [txn["description"] for txn in result] == ["In range"]


# ---------------------------------------------------------------- #
# get_category_breakdown
# ---------------------------------------------------------------- #

def test_get_category_breakdown_percentages_sum_to_100(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [
        (26.24, "Food", "2026-06-12", "Groceries at BigBasket"),
        (35.00, "Transport", "2026-06-15", "Auto fare"),
        (100.00, "Bills", "2026-06-18", "Electricity bill"),
        (45.00, "Health", "2026-06-22", "Pharmacy purchase"),
        (30.00, "Entertainment", "2026-06-26", "Movie tickets"),
        (70.00, "Shopping", "2026-06-30", "New shoes"),
        (20.00, "Other", "2026-07-04", "Miscellaneous"),
        (20.00, "Food", "2026-07-08", "Dinner with friends"),
    ])

    result = queries.get_category_breakdown(user_id)

    assert [row["name"] for row in result] == [
        "Bills", "Shopping", "Food", "Health", "Transport", "Entertainment", "Other",
    ]
    assert all(isinstance(row["pct"], int) for row in result)
    assert sum(row["pct"] for row in result) == 100


def test_get_category_breakdown_empty(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    assert queries.get_category_breakdown(user_id) == []


def test_get_category_breakdown_filtered_by_date_range(app, seeded_user):
    user_id = _user_id(seeded_user["email"])
    _insert_expenses(user_id, [
        (100.0, "Food", "2026-06-15", "In range"),
        (300.0, "Bills", "2026-07-01", "Out of range"),
    ])

    result = queries.get_category_breakdown(user_id, start_date="2026-06-01", end_date="2026-06-30")

    assert [row["name"] for row in result] == ["Food"]
    assert result[0]["pct"] == 100


# ---------------------------------------------------------------- #
# Route tests
# ---------------------------------------------------------------- #

def test_profile_redirects_when_unauthenticated(client):
    response = client.get("/profile")
    assert response.status_code == 302


def test_profile_authenticated_seed_user_shows_correct_data(client):
    db.seed_db()

    client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
    )
    response = client.get("/profile")
    body = response.data.decode()

    assert response.status_code == 200
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    assert "346.24" in body
    assert ">8<" in body
    assert "Bills" in body

    for category in [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ]:
        assert category in body

    assert body.index("Dinner with friends") < body.index("Groceries at BigBasket")
