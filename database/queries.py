from datetime import datetime

from database.db import get_db


def _date_range_filter(user_id, start_date, end_date):
    if start_date and end_date:
        return " AND date BETWEEN ? AND ?", [user_id, start_date, end_date]
    return "", [user_id]


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    date_part = row["created_at"].split(" ")[0]
    member_since = datetime.strptime(date_part, "%Y-%m-%d").strftime("%B %Y")

    return {"name": row["name"], "email": row["email"], "member_since": member_since}


def get_summary_stats(user_id, start_date=None, end_date=None):
    conn = get_db()
    try:
        date_clause, params = _date_range_filter(user_id, start_date, end_date)

        summary_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total
            FROM expenses WHERE user_id = ?{date_clause}
            """,
            params,
        ).fetchone()
        top_row = conn.execute(
            f"""
            SELECT category, SUM(amount) AS total FROM expenses
            WHERE user_id = ?{date_clause}
            GROUP BY category ORDER BY total DESC LIMIT 1
            """,
            params,
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": summary_row["total"],
        "transaction_count": summary_row["count"],
        "top_category": top_row["category"] if top_row else "—",
    }


def get_recent_transactions(user_id, limit=10, start_date=None, end_date=None):
    conn = get_db()
    try:
        date_clause, params = _date_range_filter(user_id, start_date, end_date)
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT date, description, category, amount FROM expenses
            WHERE user_id = ?{date_clause}
            ORDER BY date DESC, id DESC LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    return [dict(row) for row in rows]


def get_category_breakdown(user_id, start_date=None, end_date=None):
    conn = get_db()
    try:
        date_clause, params = _date_range_filter(user_id, start_date, end_date)

        rows = conn.execute(
            f"""
            SELECT category, SUM(amount) AS total FROM expenses
            WHERE user_id = ?{date_clause}
            GROUP BY category ORDER BY total DESC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(row["total"] for row in rows)
    breakdown = [
        {
            "name": row["category"],
            "amount": row["total"],
            "pct": round(row["total"] / grand_total * 100),
        }
        for row in rows
    ]

    remainder = 100 - sum(item["pct"] for item in breakdown)
    if remainder != 0:
        breakdown[0]["pct"] += remainder  # largest category absorbs rounding drift

    return breakdown
