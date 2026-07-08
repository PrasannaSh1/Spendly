import pytest


@pytest.fixture
def app(monkeypatch, tmp_path):
    import database.db as db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_spendly.db"))
    db.init_db()

    import app as app_module

    app_module.app.config.update(TESTING=True)
    yield app_module.app


@pytest.fixture
def seeded_user(app):
    import database.db as db

    email = "test@example.com"
    password = "correct-password"
    db.create_user("Test User", email, password)
    return {"email": email, "password": password}
