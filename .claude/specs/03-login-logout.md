# Spec: Login and Logout

## Overview
This feature implements session-based authentication for Spendly. `GET /login` already renders `login.html`, but submitting the form does nothing, and `GET /logout` is still a stub returning a raw string. This step wires up `POST /login` to verify credentials against the `users` table created in Step 1 and populated by Step 2's registration, establishes a Flask session on success, and implements `GET /logout` to clear that session. It is the first place the app tracks "who is signed in," which every later authenticated step (profile, expenses) depends on.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`).
- Step 2 — Registration (`users` rows with hashed passwords via `create_user()`).

## Routes
- `POST /login` — validate email/password against `users`, verify hash, start a session, redirect to `profile` on success or re-render `login.html` with an error on failure — public
- `GET /logout` — clear the session and redirect to `login` — logged-in (safe to call regardless of session state; no-ops if already logged out)

## Database changes
No schema changes. Add a read helper, `get_user_by_email(email)`, to `database/db.py` — no new tables/columns.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change hardcoded `<form method="POST" action="/login">` to `action="{{ url_for('login') }}"` (CLAUDE.md forbids hardcoded URLs)
  - `templates/base.html` — make the nav conditional on session state: when `session.user_id` is set, show a link to `profile` and a `logout` link instead of "Sign in" / "Get started"; reuse the existing `.nav-links a` / `.nav-cta` classes, no new CSS

## Files to change
- `app.py` — set `app.secret_key` (required for Flask sessions), change `login()` to handle `GET`/`POST`, implement `logout()` for real (replace the raw-string stub)
- `database/db.py` — add `get_user_by_email(email)` returning the full row or `None`
- `templates/login.html` — fix hardcoded form action
- `templates/base.html` — conditional nav links

## Files to create
- `tests/conftest.py` — pytest fixture providing a Flask test client against an isolated temp database
- `tests/test_login_logout.py` — automated tests for the login/logout flow

## New dependencies
No new dependencies — `pytest` and `pytest-flask` are already in `requirements.txt` (currently unused; this is the first step to add a `tests/` directory).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterized queries only — no f-strings in SQL
- Passwords verified with werkzeug's `check_password_hash` — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic (the email lookup) belongs in `database/db.py`, never inline in the route
- On failed login, use one generic error — `Invalid email or password.` — for both "no such email" and "wrong password," so the response never reveals which one was wrong
- `session['user_id']` and `session['user_name']` are the only session keys this step introduces; no "remember me" / persistent cookie behavior
- `logout()` must clear the whole session (`session.clear()`), not just one key, and must not error if no one is logged in
- `app.secret_key` must come from an environment variable with a clearly-labeled dev fallback (e.g. `os.environ.get("SECRET_KEY", "dev-secret-key-change-me")`) — do not silently ship a bare hardcoded key with no way to override it in a real deployment

## Definition of done
- [ ] Submitting `/login` with a registered email + correct password redirects to `/profile`
- [ ] After that redirect, the nav bar shows "Profile" and "Logout" instead of "Sign in" / "Get started"
- [ ] Submitting `/login` with a correct email but wrong password re-renders `login.html` with "Invalid email or password." and does not start a session
- [ ] Submitting `/login` with an email that doesn't exist re-renders `login.html` with the same "Invalid email or password." message (no distinguishable behavior from a wrong-password attempt)
- [ ] Visiting `/logout` after logging in clears the session and redirects to `/login`; the nav reverts to "Sign in" / "Get started"
- [ ] Visiting `/logout` while already logged out does not error (redirects to `/login` cleanly)
- [ ] The rendered login form's `action` uses `url_for('login')`, not a hardcoded string
- [ ] `GET /login` still renders the empty form as before
- [ ] `pytest` runs the new `tests/test_login_logout.py` and all cases pass
- [ ] App starts without errors on `python app.py` (port 5001)
