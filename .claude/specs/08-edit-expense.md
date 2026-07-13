# Spec: Edit Expense

## Overview
This feature replaces the `GET /expenses/<id>/edit` stub with a real edit flow, letting a logged-in user update an expense they previously created. It mirrors the add-expense flow (Step 7) — same fields, same validation, same categories — but pre-fills the form with the existing row and updates it in place instead of inserting a new one. It also closes a gap left by Step 7: the "Recent Transactions" list on the profile page currently has no way to reach the edit page because the expense `id` isn't surfaced there yet.

## Depends on
- Step 7 (Add Expense) — reuses `EXPENSE_CATEGORIES`, `_parse_amount()`, `_parse_expense_date()`, the `add_expense.html` form structure/CSS conventions, and the `login_required` pattern.
- Step 4/5 (Profile Page + backend routes) — the profile page and `database/queries.py` this feature must touch to add edit links.

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense's current values — logged-in only
- `POST /expenses/<int:id>/edit` — validate submitted values and update the expense, then redirect to `/profile` — logged-in only

Both routes must:
- Require login via the existing `login_required` decorator.
- Look up the expense by `id` scoped to `session["user_id"]`. If the expense doesn't exist or belongs to another user, respond with `abort(404)` — never leak whether the id exists for another account.

## Database changes
No new tables or columns. `database/db.py` currently has `create_expense()` but no read-by-id or update helper, so add:

- `get_expense_by_id(expense_id, user_id)` — `SELECT * FROM expenses WHERE id = ? AND user_id = ?`, returns the row or `None`. Parameterized, no f-strings.
- `update_expense(expense_id, user_id, amount, category, date, description)` — `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ? AND user_id = ?`. Parameterized; the `user_id` condition is the ownership guard at the DB layer, not just in the route.

Additionally, `database/queries.py`'s `get_recent_transactions()` currently selects only `date, description, category, amount` — no `id` — so the profile page has nothing to link to. Extend its `SELECT` to also return `id`.

## Templates
- **Create:** `templates/edit_expense.html` — same structure as `add_expense.html` (`.auth-section` / `.auth-container` / `.auth-header` / `.auth-card` / `.form-group` fields for amount, category, date, description), but:
  - Form fields pre-filled from the fetched expense (not `today`/blank defaults).
  - `<form method="POST" action="{{ url_for('edit_expense', id=expense.id) }}">`
  - Title/subtitle say "Edit expense" instead of "Add expense".
  - Cancel link still points to `url_for('profile')`.
- **Modify:** `templates/profile.html` — in the Recent Transactions table, add an edit link/icon per row pointing to `url_for('edit_expense', id=transaction.id)`, now that `id` is available from `get_recent_transactions()`.

## Files to change
- `app.py` — implement `edit_expense(id)` for both `GET` and `POST`, replacing the current stub.
- `database/db.py` — add `get_expense_by_id()` and `update_expense()`.
- `database/queries.py` — add `id` to the `get_recent_transactions()` SELECT.
- `templates/profile.html` — add per-row edit link.
- `CLAUDE.md` — update the "Implemented vs stub routes" table to mark `GET /expenses/<id>/edit` implemented once done (and note it's actually GET+POST).

## Files to create
- `templates/edit_expense.html`
- `static/css/edit_expense.css` — page-specific styles, mirroring `add_expense.css` conventions (select arrow styling, cancel-link hover colors) rather than duplicating them inline.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only — every `expenses` query uses `?` placeholders, never f-strings.
- Passwords hashed with werkzeug (n/a to this feature, but no regression to auth code).
- Use CSS variables — never hardcode hex values in `edit_expense.css`.
- All templates extend `base.html`.
- Reuse `_parse_amount()` and `_parse_expense_date()` from `app.py` rather than re-implementing validation.
- Reuse `EXPENSE_CATEGORIES` for the category select — do not hardcode the list again.
- Ownership check happens both in the route (404 if not found/not owned) and in the `UPDATE` statement's `WHERE` clause — defense in depth, not either/or.
- `GET /expenses/<id>/edit` on a nonexistent or non-owned id returns `404`, not a redirect or blank form.
- Do not touch `/expenses/<id>/delete` — that's Step 9, out of scope here.

## Definition of done
- [ ] Logging in, going to `/profile`, and clicking an edit link on a transaction opens `/expenses/<id>/edit` with the form pre-filled with that expense's actual amount, category, date, and description.
- [ ] Submitting the edit form with valid changes updates the row and redirects to `/profile`, where the updated values are visible.
- [ ] Submitting an invalid amount (e.g. `0`, `-5`, or non-numeric) re-renders the edit form with an error message and the submitted values retained, without touching the database.
- [ ] Submitting an invalid/missing date re-renders the form with an error message, without touching the database.
- [ ] Submitting a category not in `EXPENSE_CATEGORIES` re-renders the form with an error message.
- [ ] Visiting `/expenses/<id>/edit` for an id that doesn't exist, or that belongs to a different user, returns a 404 (verified by logging in as a second seeded user and trying the first user's expense id).
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`.
- [ ] No inline `<style>` tags were added; all new styling lives in `static/css/edit_expense.css` and uses existing CSS variables from `style.css`.
