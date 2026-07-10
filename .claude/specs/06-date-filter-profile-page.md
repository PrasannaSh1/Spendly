# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the `/profile` page. Right now the summary
stats, recent transactions list, and category breakdown always cover a user's
entire expense history. This step lets a logged-in user narrow those same
three sections down to a specific date range (e.g. "this month" or a custom
start/end date) using a simple GET-based form, without introducing any new
tables or JS frameworks.

## Depends on
- Step 1: Database setup (`expenses` table with a `date` column)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend routes for profile page (`database/queries.py` exists with
  `get_summary_stats`, `get_recent_transactions`, `get_category_breakdown`)

## Routes
- `GET /profile` — modified, not new — access level: logged-in
  - Accepts optional query string params `start_date` and `end_date`
    (`YYYY-MM-DD`)
  - When both are absent, behavior is unchanged (all-time totals)
  - When present, all three data sections (summary, transactions, category
    breakdown) are filtered to `date BETWEEN start_date AND end_date`
    (inclusive)
  - If `start_date` is after `end_date`, ignore both and fall back to
    all-time, showing a friendly inline message — do not raise an error

## Database changes
No database changes. The `expenses.date` column (`TEXT`, `YYYY-MM-DD`) already
supports range comparisons with standard `BETWEEN` / `>=` / `<=` operators.

## Templates
- **Modify:** `templates/profile.html`
  - Add a date filter form above `.profile-stats`: two `<input type="date">`
    fields (`start_date`, `end_date`) and a submit button, using `method="GET"`
    so the filter is shareable/bookmarkable via the URL
  - Add a "Clear filter" link (plain `<a href="{{ url_for('profile') }}">`)
    that only renders when a filter is active
  - When the fallback message applies (invalid range), show it near the form
  - No new template files needed

## Files to change
- `app.py` — `profile()` route reads `request.args.get("start_date")` and
  `request.args.get("end_date")`, validates them, and passes them through to
  the three query helpers
- `database/queries.py` — `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown` each gain optional `start_date=None, end_date=None`
  keyword arguments; when both are provided, an additional
  `AND date BETWEEN ? AND ?` clause is appended to the existing parameterized
  query
- `templates/profile.html` — add the filter form and clear-filter link
- `static/css/profile.css` — add styles for the new filter form (reuse
  existing CSS variables, no hardcoded hex values)

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format `start_date`/`end_date`
  into SQL, even though they come from validated query params
- Passwords hashed with werkzeug — unaffected by this step, but do not touch
  existing auth code
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate `start_date`/`end_date` format (`YYYY-MM-DD`) before passing to
  query helpers; malformed dates should be treated the same as "absent" rather
  than causing a 500 error
- If `start_date` and `end_date` are equal, treat as a single-day filter (not
  an error)
- Query helpers must still return zeroed/empty results (not raise) when the
  filtered range contains no expenses, matching existing empty-state handling
  in `get_summary_stats` / `get_recent_transactions` / `get_category_breakdown`

## Definition of done
- [ ] Visiting `/profile` with no query params shows the same all-time totals
      as before this change
- [ ] Visiting `/profile?start_date=2026-06-01&end_date=2026-06-30` (seed data)
      shows only June expenses in the summary stats, transaction list, and
      category breakdown
- [ ] The total spent, transaction count, and category percentages recompute
      correctly for the filtered range
- [ ] Submitting the filter form updates the URL with `start_date`/`end_date`
      query params (page is bookmarkable/shareable)
- [ ] A "Clear filter" link appears only when a filter is active, and clicking
      it returns to the unfiltered `/profile` view
- [ ] Submitting `start_date` after `end_date` shows a friendly message and
      falls back to all-time data instead of erroring
- [ ] A date range with zero matching expenses shows the existing empty-state
      UI (no exceptions, no broken layout)
- [ ] All amounts in the filtered view still display the ₹ symbol
