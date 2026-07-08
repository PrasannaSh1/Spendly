def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_login_success_redirects_to_profile(client, seeded_user):
    response = client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"


def test_login_success_sets_session(client, seeded_user):
    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    with client.session_transaction() as sess:
        assert sess["user_id"]
        assert sess["user_name"] == "Test User"


def test_login_wrong_password_shows_generic_error(client, seeded_user):
    response = client.post(
        "/login",
        data={"email": seeded_user["email"], "password": "wrong-password"},
    )
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_nonexistent_email_shows_same_generic_error(client, seeded_user):
    response = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "whatever123"},
    )
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_login_missing_fields_shows_generic_error(client, seeded_user):
    response = client.post(
        "/login",
        data={"email": seeded_user["email"], "password": ""},
    )
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_logout_clears_session_and_redirects(client, seeded_user):
    client.post(
        "/login",
        data={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_when_not_logged_in_does_not_error(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_login_form_action_uses_url_for(client):
    response = client.get("/login")
    assert b'action="/login"' in response.data
