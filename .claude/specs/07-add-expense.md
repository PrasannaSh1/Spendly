# Spec: Add Expense

## Overview
Step 7 turns the `/expenses/add` stub into a working feature that lets a
logged-in user record a new expense. It introduces the first write path into
the `expenses` table from the UI (previously only `seed_db()` inserted rows),
via a simple form: amount, category, date, and an optional description. On
success the user is returned to `/profile`, where the new expense
immediately shows up in the summary stats, recent transactions, and category
breakdown.

## Depends on
- Step 1: Database setup (`expenses` table already exists in
  `database/db.py`, including `user_id`, `amount`, `category`, `date`,
  `description`)
- Step 3: Login / Logout (`session["user_id"]` is set on login;
  `login_required` decorator exists in `app.py`)
- Step 5: Backend routes for profile page (`database/queries.py` pattern for
  query helpers, `profile()` route to redirect back to)

## Routes
- `GET /expenses/add` — modified (currently a stub returning a raw string) —
  access level: logged-in
  - Renders the add-expense form with empty/default fields
- `POST /expenses/add` — new — access level: logged-in
  - Reads `amount`, `category`, `date`, `description` from `request.form`
  - Validates all fields (see Rules below); on validation failure, re-renders
    the form with an inline error and the submitted values preserved
  - On success, inserts the row scoped to `session["user_id"]` and redirects
    to `url_for("profile")`

Both methods are handled by a single `add_expense()` view using
`methods=["GET", "POST"]`, matching the existing pattern used by
`register()` and `login()` in `app.py`.

## Database changes
No schema changes. The `expenses` table already has every column this
feature needs (`user_id`, `amount`, `category`, `date`, `description`).

A new write helper is needed in `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — inserts a
  row with a parameterized `INSERT` and returns `cursor.lastrowid`, following
  the same connect/try/finally-close shape as `create_user()`.

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`
  - Form fields: `amount` (`type="number"`, `step="0.01"`, `min="0.01"`),
    `category` (`<select>` with the fixed set of categories already styled
    in `profile.css`: Food, Transport, Bills, Health, Entertainment,
    Shopping, Other), `date` (`type="date"`, default value = today),
    `description` (optional `<input type="text">`)
  - `method="POST"` posting to `url_for('add_expense')`
  - Inline error message block (same visual pattern as
    `profile-filter-error` / `register.html`'s error rendering)
  - A "Cancel" link back to `url_for('profile')`
- **Modify:** none required, but `templates/profile.html` already links (or
  should link) to `/expenses/add` — if no such link exists yet, add a
  "Add expense" button/link near `.profile-header` pointing to
  `url_for('add_expense')`

## Files to change
- `app.py`
  - Replace the `add_expense()` stub with a real `GET`/`POST` view, decorated
    with `@login_required`
  - Import `create_expense` from `database.db`
  - Add a small `_parse_amount(raw)` / validation helper near the existing
    `_parse_date_range()` helper if validation logic grows beyond a few
    lines (keep the route itself to fetch-validate-redirect only)
- `database/db.py` — add `create_expense()` helper
- `templates/profile.html` — add an "Add expense" link if not already present

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` (page-specific styles, reusing existing CSS
  variables from `style.css` / `profile.css` — e.g. `--accent`,
  `--danger`, `--border-soft`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never f-strings/string-format user input into
  SQL
- Passwords hashed with werkzeug — unaffected by this step
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `amount` must be a positive number (`> 0`); reject non-numeric or
  zero/negative input with a friendly inline error, not a 500
- `category` must be one of the fixed set of known categories (Food,
  Transport, Bills, Health, Entertainment, Shopping, Other); reject anything
  else server-side even though the `<select>` constrains it client-side
- `date` must be a valid `YYYY-MM-DD` date; reject malformed input with a
  friendly inline error (reuse the `strptime` pattern from
  `_parse_date_range()`)
- `description` is optional — store `None`/empty as-is, matching existing
  `expenses.description` nullable behavior
- The inserted expense's `user_id` must always come from
  `session["user_id"]`, never from form input, so a user can only ever add
  expenses to their own account
- Route function stays thin: parse/validate form data, call
  `create_expense()`, redirect — no inline SQL in `app.py`

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows a form with amount,
      category, date (defaulted to today), and description fields
- [ ] Submitting valid data creates a new row in `expenses` scoped to the
      current user and redirects to `/profile`
- [ ] The new expense immediately appears in `/profile`'s recent
      transactions, updates the total spent, and is reflected in the
      category breakdown
- [ ] Submitting a zero, negative, or non-numeric amount re-renders the form
      with an inline error and preserves the other submitted values
- [ ] Submitting an invalid/malformed date re-renders the form with an
      inline error instead of raising a 500
- [ ] Submitting an unrecognized category value (e.g. via a crafted request)
      is rejected server-side with an inline error
- [ ] All amounts and form labels display the ₹ symbol, not `$`
- [ ] The new expense's amount displays correctly formatted (e.g. `₹1,234.50`)
      once shown on `/profile`
