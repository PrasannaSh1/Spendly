# Spec: Registration

## Overview
This feature implements account creation for Spendly. The `GET /register` route already renders `register.html`, but submitting the form does nothing — there is no `POST /register` handler. This step wires up the form to validate input, hash the password, insert a new row into the `users` table, and redirect the user to the login page. It builds directly on the database layer from Step 1 (`database/db.py`) and is a prerequisite for every later step that requires an authenticated user (login/session, profile, expenses).

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`) must already be complete.

## Routes
- `POST /register` — validate name/email/password, hash password, insert user, redirect to `login` on success or re-render `register.html` with an error on failure — public

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) already supports this feature. Use parameterized `INSERT` against the existing schema.

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — change the hardcoded `<form method="POST" action="/register">` to `action="{{ url_for('register') }}"` (CLAUDE.md forbids hardcoded URLs); the existing `{% if error %}` block already supports displaying a validation/duplicate-email error passed from the route.

## Files to change
- `app.py` — change `register()` to handle `GET` and `POST`; on `POST`, validate input and call the new DB helper, then redirect or re-render with an error
- `database/db.py` — add a `create_user(name, email, password_hash)` helper (or equivalent) so DB logic stays out of `app.py`; use a parameterized `INSERT` and let the existing `UNIQUE` constraint on `email` surface duplicates
- `templates/register.html` — fix hardcoded form action

## Files to create
None.

## New dependencies
No new dependencies — `werkzeug.security.generate_password_hash` is already available and used in `database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterized queries only — no f-strings in SQL
- Passwords hashed with werkzeug (`generate_password_hash`) — never store plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic (the insert, the duplicate-email check) belongs in `database/db.py`, never inline in the route
- Validate on the server even though the form has `required`/`type=email` — do not trust client-side validation alone
- Enforce the same minimum password length the placeholder already advertises ("Min. 8 characters")
- On duplicate email, re-render `register.html` with a friendly error via the existing `error` template variable — do not leak whether it was the email or another field via a raw DB exception
- No session/login is created on successful registration — that belongs to the login step; redirect to `url_for('login')`

## Definition of done
- [ ] Submitting the register form with a new name/email/password creates a row in `users` with a hashed (not plaintext) password
- [ ] After successful registration, the browser is redirected to `/login`
- [ ] Submitting with an email that already exists re-renders `register.html` showing an error, and does not create a duplicate row
- [ ] Submitting with a password under 8 characters re-renders `register.html` with a validation error and no row is created
- [ ] Submitting with a missing name/email/password re-renders `register.html` with a validation error and no row is created
- [ ] The rendered form's `action` uses `url_for('register')`, not a hardcoded string
- [ ] `GET /register` still renders the empty form as before
- [ ] App starts without errors on `python app.py` (port 5001)
