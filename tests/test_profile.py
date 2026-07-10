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


def test_profile_redirects_to_login_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302


def test_profile_clears_stale_session_for_deleted_user(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 999
        sess["user_name"] = "Ghost User"

    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    assert response.headers["Location"] == "/login"


def test_profile_shows_name_and_email(client, seeded_user):
    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"Test User" in response.data
    assert b"test@example.com" in response.data


def test_profile_zero_expenses_shows_empty_state(client, seeded_user):
    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile")
    assert b"No expenses yet" in response.data
    assert b"No category data yet" in response.data
    assert "₹0.00".encode() in response.data
    assert "—".encode() in response.data  # top category placeholder


def test_profile_shows_correct_summary_and_recent_order(client, seeded_user):
    conn = db.get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?", (seeded_user["email"],)
    ).fetchone()
    conn.close()

    _insert_expenses(user["id"], [
        (100.0, "Food", "2026-07-01", "Oldest"),
        (200.0, "Transport", "2026-07-02", "Second"),
        (300.0, "Bills", "2026-07-03", "Third"),
        (400.0, "Health", "2026-07-04", "Fourth"),
        (500.0, "Entertainment", "2026-07-05", "Fifth"),
        (600.0, "Shopping", "2026-07-06", "Sixth"),
        (700.0, "Food", "2026-07-07", "Seventh"),
        (800.0, "Transport", "2026-07-08", "Eighth"),
        (900.0, "Bills", "2026-07-09", "Ninth"),
        (1000.0, "Health", "2026-07-10", "Tenth"),
        (1100.0, "Entertainment", "2026-07-11", "Newest"),
    ])

    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile")
    assert response.status_code == 200

    body = response.data.decode()

    # total = 100+200+...+1100 = 6600.00, count = 11
    assert "6,600.00" in body
    assert ">11<" in body

    # only 10 most recent shown, newest first, oldest excluded
    assert "Newest" in body
    assert "Tenth" in body
    assert "Ninth" in body
    assert "Eighth" in body
    assert "Seventh" in body
    assert "Sixth" in body
    assert "Oldest" not in body

    assert body.index("Newest") < body.index("Tenth")

    # By Category panel present, top category (highest total) is Shopping
    assert "By Category" in body
    assert "Top category" in body


def test_profile_route_applies_valid_date_filter(client, seeded_user):
    conn = db.get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?", (seeded_user["email"],)
    ).fetchone()
    conn.close()

    _insert_expenses(user["id"], [
        (100.0, "Food", "2026-06-15", "June expense"),
        (500.0, "Bills", "2026-07-01", "July expense"),
    ])

    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile?start_date=2026-06-01&end_date=2026-06-30")
    body = response.data.decode()

    assert response.status_code == 200
    assert "June expense" in body
    assert "July expense" not in body
    assert "100.00" in body
    assert "Clear filter" in body


def test_profile_route_invalid_range_falls_back_with_message(client, seeded_user):
    conn = db.get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?", (seeded_user["email"],)
    ).fetchone()
    conn.close()

    _insert_expenses(user["id"], [(100.0, "Food", "2026-06-15", "Should still show")])

    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile?start_date=2026-07-01&end_date=2026-06-01")
    body = response.data.decode()

    assert response.status_code == 200
    assert "Should still show" in body
    assert "Clear filter" not in body
    assert "before end date" in body


def test_profile_route_malformed_date_treated_as_absent(client, seeded_user):
    conn = db.get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?", (seeded_user["email"],)
    ).fetchone()
    conn.close()

    _insert_expenses(user["id"], [(100.0, "Food", "2026-06-15", "Still shown")])

    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile?start_date=not-a-date&end_date=2026-06-30")
    body = response.data.decode()

    assert response.status_code == 200
    assert "Still shown" in body
    assert "Clear filter" not in body
    assert "before end date" not in body


def test_profile_route_no_params_unchanged(client, seeded_user):
    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile")
    assert response.status_code == 200
    assert "Clear filter" not in response.data.decode()


def test_profile_route_filter_zero_matches_shows_empty_state(client, seeded_user):
    conn = db.get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?", (seeded_user["email"],)
    ).fetchone()
    conn.close()

    _insert_expenses(user["id"], [(100.0, "Food", "2026-07-01", "Out of range")])

    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
    body = response.data.decode()

    assert response.status_code == 200
    assert "No expenses yet" in body
    assert "No category data yet" in body
    assert "₹0.00" in body
    assert "Clear filter" in body
