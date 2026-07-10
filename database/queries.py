from datetime import datetime

from database.db import get_db


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


def get_summary_stats(user_id):
    conn = get_db()
    try:
        summary_row = conn.execute(
            """
            SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total
            FROM expenses WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        top_row = conn.execute(
            """
            SELECT category, SUM(amount) AS total FROM expenses
            WHERE user_id = ? GROUP BY category ORDER BY total DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": summary_row["total"],
        "transaction_count": summary_row["count"],
        "top_category": top_row["category"] if top_row else "—",
    }


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT date, description, category, amount FROM expenses
            WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    return [dict(row) for row in rows]


def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS total FROM expenses
            WHERE user_id = ? GROUP BY category ORDER BY total DESC
            """,
            (user_id,),
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
