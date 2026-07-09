# Spec: Profile Page Design

## Overview
Spendly currently redirects a logged-in user to `/profile` after login, but the route just returns a raw placeholder string. This step replaces that stub with a real, styled profile page: it shows who the logged-in user is (name, email, member-since date) and a quick snapshot of their expense activity (total spent, number of expenses, and a short list of their most recent expenses). It is the first page in the app that reads authenticated, user-scoped data, and it establishes the `login_required` pattern that later steps (add/edit/delete expense) will reuse.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`, `init_db()`).
- Step 2 — Registration (`create_user()`).
- Step 3 — Login and Logout (`session['user_id']` / `session['user_name']`, conditional nav in `base.html`).

## Routes
- `GET /profile` — render the logged-in user's profile and expense summary — logged-in only (unauthenticated visitors are redirected to `login`)

## Database changes
No new tables or columns. The existing `users` and `expenses` tables already have everything needed. Add three read-only helpers to `database/db.py`:
- `get_user_by_id(user_id)` — `SELECT * FROM users WHERE id = ?`, returns the row or `None` (the session only stores `user_id`/`user_name`, not `email`/`created_at`, so profile needs a fresh lookup)
- `get_expense_summary(user_id)` — `SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ?`, returns a dict/row with `count` and `total`
- `get_recent_expenses(user_id, limit=5)` — `SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?`, returns up to `limit` rows

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; shows a header with the user's name/email/member-since date, a stats row (total spent, expense count) styled after the existing `.mock-stat` card pattern, and a "Recent expenses" list/table built from `get_recent_expenses`. If there are zero expenses, show a simple empty-state message instead of an empty table.
- **Modify:** none — `base.html` nav already links to `profile` and `logout` when `session.user_id` is set.

## Files to change
- `app.py` — add a small `login_required` decorator (checks `session.get("user_id")`, redirects to `url_for("login")` if absent) and apply it to `profile()`; implement `profile()` to fetch the user, summary, and recent expenses, then render `profile.html`
- `database/db.py` — add `get_user_by_id`, `get_expense_summary`, `get_recent_expenses`

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles for the profile header, stats row, and recent-expenses list (reuse `--accent`, `--paper-card`, `--border`, etc. from `style.css`; no hardcoded hex values)
- `tests/test_profile.py` — automated tests for the new route

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterized queries only — no f-strings in SQL
- Passwords are never touched by this step (no password field is displayed or edited)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic (user lookup, expense summary, recent expenses) belongs in `database/db.py`, never inline in the route
- `profile()` is read-only for this step — no editing name/email/password here (that is a future step, not part of "profile page design")
- Do not touch `/expenses/add`, `/expenses/<id>/edit`, or `/expenses/<id>/delete` — those stay stubs per CLAUDE.md until Steps 7–9
- `login_required` must redirect (not `abort()`) unauthenticated users to `login`, since there is no session to show an error against
- Currency values are formatted in INR (`₹`), matching the seeded demo data in `database/db.py`

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as the seeded demo user (`demo@spendly.com` / `demo123`) and visiting `/profile` shows that user's name, email, and member-since date
- [ ] The profile page shows the correct total spent (₹) and total expense count for that user, matching the seeded `expenses` rows
- [ ] The profile page lists up to 5 of the user's most recent expenses, ordered newest-first
- [ ] A user with zero expenses sees an empty-state message instead of a broken/empty table
- [ ] The page uses only CSS variables already defined in `style.css` (or new ones added to `:root`), no hardcoded hex colors
- [ ] `pytest` runs `tests/test_profile.py` and all cases pass
- [ ] App starts without errors on `python app.py` (port 5001)
