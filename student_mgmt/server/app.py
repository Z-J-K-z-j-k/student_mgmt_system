# server/app.py
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import check_password_hash
from pathlib import Path
from .models import get_conn
from .analysis import get_overall_stats, histogram_bins
from .charts import generate_score_histogram, generate_major_pie
from .crawler import crawl_dummy_students
from .llm_api import ask_llm
from .config import CHART_DIR

app = Flask(__name__)

# ---------- 登录与用户 ----------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND role=?", (username, role))
        row = cur.fetchone()

    if row is None:
        return jsonify({"status": "error", "msg": "用户不存在或角色不匹配"})

    if not check_password_hash(row["password_hash"], password):
        return jsonify({"status": "error", "msg": "密码错误"})

    return jsonify({
        "status": "ok",
        "user_id": row["id"],
        "role": row["role"],
        "real_name": row["real_name"] or row["username"],
        "token": f"TOKEN-{row['id']}"
    })

# ---------- 学生 CRUD + 搜索 + 分页 ----------

@app.route("/api/students", methods=["GET"])
def list_students():
    # 参数：page, page_size, keyword, class_name
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword", "").strip()
    class_name = request.args.get("class_name", "").strip()

    where = []
    params = []
    if keyword:
        where.append("(student_no LIKE ? OR name LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])
    if class_name:
        where.append("class_name = ?")
        params.append(class_name)

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM students {where_sql}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT * FROM students
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    students = [dict(r) for r in rows]
    return jsonify({
        "status": "ok",
        "data": students,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@app.route("/api/students", methods=["POST"])
def create_student():
    data = request.json or {}
    fields = ("student_no", "name", "gender", "major", "class_name", "phone", "email")
    values = [data.get(f) for f in fields]

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO students (student_no, name, gender, major, class_name, phone, email)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, values)
        new_id = cur.lastrowid

    return jsonify({"status": "ok", "id": new_id})

@app.route("/api/students/<int:sid>", methods=["PUT"])
def update_student(sid):
    data = request.json or {}
    fields = ("student_no", "name", "gender", "major", "class_name", "phone", "email")
    values = [data.get(f) for f in fields]

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE students
        SET student_no=?, name=?, gender=?, major=?, class_name=?, phone=?, email=?
        WHERE id=?
        """, values + [sid])

    return jsonify({"status": "ok"})

@app.route("/api/students/<int:sid>", methods=["DELETE"])
def delete_student(sid):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM students WHERE id=?", (sid,))
    return jsonify({"status": "ok"})

# ---------- 教师 / 课程 / 成绩 CRUD（简单版，与学生类似） ----------

@app.route("/api/teachers", methods=["GET"])
def list_teachers():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM teachers ORDER BY id DESC")
        rows = cur.fetchall()
    return jsonify({"status": "ok", "data": [dict(r) for r in rows]})

@app.route("/api/courses", methods=["GET"])
def list_courses():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT c.*, t.name AS teacher_name
        FROM courses c
        LEFT JOIN teachers t ON c.teacher_id = t.id
        ORDER BY c.id DESC
        """)
        rows = cur.fetchall()
    return jsonify({"status": "ok", "data": [dict(r) for r in rows]})

@app.route("/api/scores", methods=["GET"])
def list_scores():
    student_id = request.args.get("student_id")
    where = []
    params = []
    if student_id:
        where.append("e.student_id=?")
        params.append(student_id)
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT e.id, s.student_no, s.name AS student_name,
               c.course_no, c.name AS course_name,
               e.score, e.term
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c  ON e.course_id = c.id
        {where_sql}
        ORDER BY e.id DESC
        """, params)
        rows = cur.fetchall()
    return jsonify({"status": "ok", "data": [dict(r) for r in rows]})

@app.route("/api/scores", methods=["POST"])
def add_score():
    data = request.json or {}
    student_id = data.get("student_id")
    course_id = data.get("course_id")
    score = data.get("score")
    term = data.get("term")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO enrollments (student_id, course_id, score, term)
        VALUES (?, ?, ?, ?)
        """, (student_id, course_id, score, term))
    return jsonify({"status": "ok"})

@app.route("/api/scores/<int:eid>", methods=["PUT"])
def update_score(eid):
    data = request.json or {}
    score = data.get("score")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE enrollments SET score=? WHERE id=?", (score, eid))
    return jsonify({"status": "ok"})

# ---------- 统计分析 & 图表 ----------

@app.route("/api/stats/overview", methods=["GET"])
def stats_overview():
    return jsonify({"status": "ok", "data": get_overall_stats()})

@app.route("/api/stats/histogram", methods=["GET"])
def stats_hist():
    return jsonify({"status": "ok", "data": histogram_bins()})

@app.route("/api/charts/<string:chart_name>", methods=["GET"])
def get_chart(chart_name):
    Path(CHART_DIR).mkdir(parents=True, exist_ok=True)
    if chart_name == "score_hist.png":
        path = generate_score_histogram()
    elif chart_name == "major_pie.png":
        path = generate_major_pie()
    else:
        return jsonify({"status": "error", "msg": "未知图表"}), 404

    directory = str(Path(path).parent)
    fname = Path(path).name
    return send_from_directory(directory, fname)

# ---------- 爬虫触发 ----------

@app.route("/api/crawler/run", methods=["POST"])
def run_crawler():
    count = crawl_dummy_students()
    return jsonify({"status": "ok", "added": count})

# ---------- 大模型接口 ----------

@app.route("/api/llm_chat", methods=["POST"])
def llm_chat():
    data = request.json or {}
    prompt = data.get("prompt", "")
    reply = ask_llm(prompt)
    return jsonify({"status": "ok", "reply": reply})

if __name__ == "__main__":
    # 生产环境你可以关 debug
    app.run(host="0.0.0.0", port=5000, debug=True)
