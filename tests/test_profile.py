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
        (600.0, "Shopping", "2026-07-06", "Newest"),
    ])

    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/profile")
    assert response.status_code == 200

    body = response.data.decode()

    # total = 100+200+300+400+500+600 = 2100.00, count = 6
    assert "2,100.00" in body
    assert ">6<" in body

    # only 5 most recent shown, newest first, oldest excluded
    assert "Newest" in body
    assert "Fifth" in body
    assert "Fourth" in body
    assert "Third" in body
    assert "Second" in body
    assert "Oldest" not in body

    assert body.index("Newest") < body.index("Second")

    # By Category panel present, top category (highest total) is Shopping
    assert "By Category" in body
    assert "Top category" in body
