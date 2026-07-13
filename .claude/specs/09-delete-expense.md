# Spec: Delete Expense

## Overview
This feature replaces the `/expenses/<id>/delete` stub with a real delete flow, letting a logged-in user permanently remove an expense they previously created, directly from the "Recent Transactions" list on their profile page. It closes out the core expense CRUD loop started by add (Step 7) and edit (Step 8). Since deletion is destructive and irreversible, the row's "Delete" action asks for confirmation client-side before submitting.

## Depends on
- Step 7 (Add Expense) / Step 8 (Edit Expense) — reuses the `login_required` decorator and the ownership-check pattern established by `edit_expense`: fetch via `get_expense_by_id(id, session["user_id"])`, `abort(404)` if `None`.
- Step 5/6 (Profile backend + date filter) — deleting a row must be reflected in the same `/profile` view (summary stats, recent transactions, category breakdown) since they all read from the same `expenses` table.

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense, then redirect to `/profile` — logged-in only

This is POST-only, not GET — a destructive action must never be triggered by a plain GET request (link prefetching, crawlers, or a user just visiting the URL should never delete data). Visiting it with GET returns Flask's default `405 Method Not Allowed`.

Must:
- Require login via `login_required`.
- Look up the expense scoped to `session["user_id"]` via `get_expense_by_id`. If `None` (doesn't exist or belongs to another user), `abort(404)`.

## Database changes
No new tables or columns. Add to `database/db.py`, following the exact pattern of `update_expense()`:

- `delete_expense(expense_id, user_id)` — `DELETE FROM expenses WHERE id = ? AND user_id = ?`. Parameterized; the `user_id` clause is the DB-layer ownership guard (defense in depth alongside the route-level `get_expense_by_id` check), same reasoning as Step 8.

## Templates
- **Create:** none.
- **Modify:** `templates/profile.html` — in the Recent Transactions table, add a "Delete" action next to the existing "Edit" link in the same action cell (no new `<th>`/`<td>` column needed). Implemented as a small `<form method="POST" action="{{ url_for('delete_expense', id=txn.id) }}">` containing a single submit button styled to look like a link (`.profile-table-delete-link`), sitting next to the existing `.profile-table-edit-link` anchor.

## Files to change
- `app.py` — implement `delete_expense(id)` for `POST` only, replacing the current stub.
- `database/db.py` — add `delete_expense()`.
- `templates/profile.html` — add the delete form/button per transaction row.
- `static/css/profile.css` — add `.profile-table-delete-link` styling using `--danger`/`--danger-light` (already defined, already used elsewhere in this file).
- `static/js/main.js` — add a small vanilla-JS confirm-before-submit handler for delete forms (currently this file is empty except a placeholder comment).
- `CLAUDE.md` — update the "Implemented vs stub routes" table: `GET /expenses/<id>/delete` → `POST /expenses/<id>/delete`, marked implemented.

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only — the `DELETE` statement uses `?` placeholders, never f-strings.
- Passwords hashed with werkzeug (n/a to this feature, no regression to auth code).
- Use CSS variables — never hardcode hex values in `profile.css`; reuse `--danger`/`--danger-light`.
- All templates extend `base.html` (no new templates added by this feature).
- The route accepts `POST` only — no `GET` handling, no `methods=["GET", "POST"]`.
- Ownership check happens both in the route (`abort(404)` on `None` from `get_expense_by_id`) and in the `DELETE` statement's `WHERE` clause.
- Client-side confirmation must live in `static/js/main.js` as a reusable handler (e.g. attach to `form.delete-expense-form` submit events, `confirm(...)`, `event.preventDefault()` on cancel) — no inline `<script>` blocks in `profile.html`.
- Do not modify `/expenses/<id>/edit` or `edit_expense.html` — that's Step 8, already implemented, out of scope here.
- Do not add a separate "are you sure" confirmation page/route — the native `confirm()` dialog is sufficient for this step.

## Definition of done
- [ ] Logging in, going to `/profile`, and clicking "Delete" on a transaction shows a browser `confirm()` dialog before anything happens.
- [ ] Cancelling the confirm dialog leaves the expense untouched — no request is sent, the row is still present after cancelling.
- [ ] Confirming the dialog deletes the expense, redirects to `/profile`, and the row no longer appears in Recent Transactions.
- [ ] After deleting, the "Total spent" / "Transactions" summary stats and the "By Category" breakdown on `/profile` reflect the removal (they read from the same table, so no separate update logic is needed — just verify the numbers actually changed).
- [ ] Sending `POST /expenses/<id>/delete` for a nonexistent id, or an id belonging to a different user, returns 404 (verify with a second seeded user and their own expense id).
- [ ] Visiting `GET /expenses/<id>/delete` directly (e.g. typing the URL in the browser) returns 405, not a deletion.
- [ ] Accessing the delete route while logged out redirects to `/login`.
- [ ] No inline `<script>` or `<style>` tags were added; the confirm-before-delete logic lives in `static/js/main.js` and all new CSS uses existing variables from `static/css/style.css`.
