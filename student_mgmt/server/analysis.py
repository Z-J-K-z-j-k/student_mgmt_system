# server/analysis.py
import pandas as pd
from .models import get_conn

def load_scores_df():
    with get_conn() as conn:
        df = pd.read_sql_query("""
        SELECT e.id, s.student_no, s.name AS student_name,
               c.course_no, c.name AS course_name,
               e.score, e.term, s.major, s.class_name
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c  ON e.course_id = c.id
        """, conn)
    return df

def get_overall_stats():
    df = load_scores_df()
    if df.empty:
        return {
            "total_records": 0,
            "avg_score": None,
            "pass_rate": None,
            "excellent_rate": None
        }

    total = len(df)
    avg = float(df["score"].mean())
    pass_rate = float((df["score"] >= 60).mean())
    excellent_rate = float((df["score"] >= 90).mean())

    by_major = df.groupby("major")["score"].mean().to_dict()
    by_class = df.groupby("class_name")["score"].mean().to_dict()

    return {
        "total_records": total,
        "avg_score": round(avg, 2),
        "pass_rate": round(pass_rate, 4),
        "excellent_rate": round(excellent_rate, 4),
        "avg_by_major": by_major,
        "avg_by_class": by_class
    }

def histogram_bins():
    df = load_scores_df()
    if df.empty:
        return []

    bins = [0, 60, 70, 80, 90, 100]
    labels = ["0-59", "60-69", "70-79", "80-89", "90-100"]
    cut = pd.cut(df["score"], bins=bins, labels=labels, include_lowest=True)
    counts = cut.value_counts().sort_index()
    return [{"range": idx, "count": int(c)} for idx, c in counts.items()]
