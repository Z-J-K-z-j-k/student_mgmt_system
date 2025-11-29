# server/app.py
import sys
import hashlib
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import check_password_hash

# 兼容直接运行脚本（python student_mgmt/server/app.py）
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from server.models import get_conn
    from server.analysis import (
        get_overall_stats, histogram_bins, get_school_stats, get_top_students,
        get_course_avg_comparison, get_major_stats, get_grade_stats, check_data_quality
    )
    from server.charts import (
        generate_score_histogram, generate_major_pie, generate_major_avg_bar,
        generate_grade_trend, generate_course_comparison, generate_score_distribution_pie
    )
    from server.crawler import crawl_dummy_students, crawl_bupt_scs_teachers
    from server.llm_api import ask_llm
    from server.config import CHART_DIR
else:
    from .models import get_conn
    from .analysis import (
        get_overall_stats, histogram_bins, get_school_stats, get_top_students,
        get_course_avg_comparison, get_major_stats, get_grade_stats, check_data_quality
    )
    from .charts import (
        generate_score_histogram, generate_major_pie, generate_major_avg_bar,
        generate_grade_trend, generate_course_comparison, generate_score_distribution_pie
    )
    from .crawler import crawl_dummy_students, crawl_bupt_scs_teachers
    from .llm_api import ask_llm
    from .config import CHART_DIR

app = Flask(__name__)


def score_to_gpa(score):
    """
    将百分制成绩转换为GPA（0-4体系）
    转换规则：
    90-100 -> 4.0
    85-89  -> 3.7
    82-84  -> 3.3
    78-81  -> 3.0
    75-77  -> 2.7
    72-74  -> 2.3
    68-71  -> 2.0
    66-67  -> 1.7
    64-65  -> 1.5
    60-63  -> 1.0
    0-59   -> 0.0
    """
    if score is None:
        return None
    try:
        score = float(score)
        if score >= 90:
            return 4.0
        elif score >= 85:
            return 3.7
        elif score >= 82:
            return 3.3
        elif score >= 78:
            return 3.0
        elif score >= 75:
            return 2.7
        elif score >= 72:
            return 2.3
        elif score >= 68:
            return 2.0
        elif score >= 66:
            return 1.7
        elif score >= 64:
            return 1.5
        elif score >= 60:
            return 1.0
        else:
            return 0.0
    except (ValueError, TypeError):
        return None


def calculate_gpa_and_weighted_avg(scores_data):
    """
    计算GPA和加权平均分
    scores_data: 成绩数据列表，每个元素应包含 score 和 credit 字段
    
    返回: (gpa, weighted_avg, total_credits)
    """
    valid_courses = []
    for item in scores_data:
        score = item.get("score")
        credit = item.get("credit")
        
        # 只计算有成绩和学分的课程
        if score is not None and credit is not None:
            try:
                score_val = float(score)
                credit_val = float(credit)
                if 0 <= score_val <= 100 and credit_val > 0:
                    valid_courses.append({
                        "score": score_val,
                        "credit": credit_val
                    })
            except (ValueError, TypeError):
                continue
    
    if not valid_courses:
        return None, None, 0
    
    # 计算加权平均分
    total_weighted_score = sum(c["score"] * c["credit"] for c in valid_courses)
    total_credits = sum(c["credit"] for c in valid_courses)
    weighted_avg = total_weighted_score / total_credits if total_credits > 0 else 0
    
    # 计算GPA
    total_gpa_points = 0
    for c in valid_courses:
        gpa_point = score_to_gpa(c["score"])
        if gpa_point is not None:
            total_gpa_points += gpa_point * c["credit"]
    
    gpa = total_gpa_points / total_credits if total_credits > 0 else 0
    
    return round(gpa, 2), round(weighted_avg, 2), total_credits


def _extract_user_id(token: str):
    if not token or not token.startswith("TOKEN-"):
        return None
    try:
        return int(token.replace("TOKEN-", "", 1))
    except ValueError:
        return None


def _get_user_from_token(token: str):
    user_id = _extract_user_id(token)
    if not user_id:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, role FROM users WHERE user_id=%s", (user_id,))
        return cur.fetchone()


def _build_user_context(user):
    """
    根据当前用户角色拼装背景信息，供大模型参考。
    """
    if not user:
        return ""

    role = user.get("role")
    user_id = user.get("user_id")
    if not user_id:
        return ""

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            if role == "student":
                # 获取学生基本信息
                cur.execute(
                    """
                    SELECT student_id, name, major, grade, class_name, gpa, phone, email
                    FROM students
                    WHERE user_id=%s
                    """,
                    (user_id,),
                )
                profile = cur.fetchone()
                if not profile:
                    return ""
                student_id = profile["student_id"]
                summary = [
                    f"【学生信息】",
                    f"姓名：{profile.get('name') or '未知'}",
                    f"专业：{profile.get('major') or '未填写'}",
                    f"年级：{profile.get('grade') or '未填写'}",
                    f"班级：{profile.get('class_name') or '未填写'}",
                ]
                gpa = profile.get("gpa")
                if gpa is not None:
                    summary.append(f"GPA：{gpa:.2f}")

                # 获取所有成绩信息（用于分析）
                cur.execute(
                    """
                    SELECT c.course_name, c.credit, sc.score, sc.exam_date, cs.semester
                    FROM scores sc
                    JOIN course_selection cs ON sc.selection_id = cs.selection_id
                    JOIN courses c ON cs.course_id = c.course_id
                    WHERE cs.student_id=%s AND sc.score IS NOT NULL
                    ORDER BY sc.exam_date DESC
                    """,
                    (student_id,),
                )
                all_scores = cur.fetchall()
                
                if all_scores:
                    # 计算统计信息
                    total_credits = sum(row.get('credit', 0) or 0 for row in all_scores)
                    total_score_weighted = sum((row.get('score', 0) or 0) * (row.get('credit', 0) or 0) for row in all_scores)
                    weighted_avg = total_score_weighted / total_credits if total_credits > 0 else 0
                    
                    # 按分数段统计
                    excellent = sum(1 for row in all_scores if (row.get('score') or 0) >= 90)
                    good = sum(1 for row in all_scores if 80 <= (row.get('score') or 0) < 90)
                    pass_count = sum(1 for row in all_scores if 60 <= (row.get('score') or 0) < 80)
                    fail = sum(1 for row in all_scores if (row.get('score') or 0) < 60)
                    
                    summary.append(f"\n【成绩统计】")
                    summary.append(f"已修课程数：{len(all_scores)}门")
                    summary.append(f"总学分：{total_credits}")
                    summary.append(f"加权平均分：{weighted_avg:.2f}分")
                    summary.append(f"优秀(≥90分)：{excellent}门，良好(80-89分)：{good}门，及格(60-79分)：{pass_count}门，不及格(<60分)：{fail}门")
                    
                    # 最近5门课程成绩
                    summary.append(f"\n【最近成绩】")
                    recent_scores = all_scores[:5]
                    for row in recent_scores:
                        course_name = row.get('course_name', '未知')
                        score = row.get('score', 0)
                        credit = row.get('credit', 0) or 0
                        semester = row.get('semester', '')
                        info = f"{course_name}：{score}分（{credit}学分"
                        if semester:
                            info += f"，{semester}"
                        info += "）"
                        summary.append(info)
                    
                    # 薄弱科目（低于70分的课程）
                    weak_courses = [row for row in all_scores if (row.get('score') or 0) < 70]
                    if weak_courses:
                        summary.append(f"\n【需要关注的课程】")
                        for row in weak_courses[:5]:  # 最多显示5门
                            summary.append(f"{row.get('course_name', '未知')}：{row.get('score', 0)}分")
                
                # 获取已选但未出成绩的课程
                cur.execute(
                    """
                    SELECT c.course_name, c.credit, cs.semester
                    FROM course_selection cs
                    JOIN courses c ON cs.course_id = c.course_id
                    LEFT JOIN scores sc ON sc.selection_id = cs.selection_id
                    WHERE cs.student_id=%s AND sc.score IS NULL
                    ORDER BY cs.semester DESC
                    LIMIT 5
                    """,
                    (student_id,),
                )
                pending_courses = cur.fetchall()
                if pending_courses:
                    summary.append(f"\n【待出成绩的课程】")
                    for row in pending_courses:
                        info = f"{row.get('course_name', '未知')}（{row.get('credit', 0)}学分"
                        if row.get('semester'):
                            info += f"，{row['semester']}"
                        info += "）"
                        summary.append(info)
                
                return "\n".join(summary)

            if role == "teacher":
                # 获取教师基本信息
                cur.execute(
                    """
                    SELECT teacher_id, name, department, title, research, phone, email
                    FROM teachers
                    WHERE user_id=%s
                    """,
                    (user_id,),
                )
                profile = cur.fetchone()
                if not profile:
                    return ""
                
                teacher_id = profile["teacher_id"]
                summary = [
                    f"【教师信息】",
                    f"姓名：{profile.get('name') or '未知'}",
                    f"所属部门：{profile.get('department') or '未填写'}",
                    f"职称：{profile.get('title') or '未填写'}",
                ]
                
                # 添加研究方向
                research = profile.get("research")
                if research:
                    summary.append(f"研究方向：{research}")
                
                # 获取教师教授的课程及详细统计信息
                cur.execute(
                    """
                    SELECT
                        c.course_id,
                        c.course_name,
                        c.credit,
                        cs.semester,
                        COUNT(DISTINCT cs.student_id) AS total_students,
                        COUNT(s.score_id) AS scored_students,
                        AVG(s.score) AS avg_score,
                        MIN(s.score) AS min_score,
                        MAX(s.score) AS max_score,
                        SUM(CASE WHEN s.score >= 90 THEN 1 ELSE 0 END) AS excellent_count,
                        SUM(CASE WHEN s.score >= 60 AND s.score < 90 THEN 1 ELSE 0 END) AS pass_count,
                        SUM(CASE WHEN s.score < 60 THEN 1 ELSE 0 END) AS fail_count
                    FROM courses c
                    LEFT JOIN course_selection cs ON c.course_id = cs.course_id
                    LEFT JOIN scores s ON cs.selection_id = s.selection_id AND s.score IS NOT NULL
                    WHERE c.teacher_id = %s
                    GROUP BY c.course_id, c.course_name, c.credit, cs.semester
                    ORDER BY c.course_id DESC
                    """,
                    (teacher_id,),
                )
                courses = cur.fetchall()
                
                if courses:
                    summary.append(f"\n【教授的课程】共{len(courses)}门")
                    
                    # 总体统计
                    total_students_all = sum(c.get("total_students", 0) or 0 for c in courses)
                    total_scored = sum(c.get("scored_students", 0) or 0 for c in courses)
                    summary.append(f"总选课人数：{total_students_all}人，已有成绩：{total_scored}人")
                    
                    # 每门课程的详细信息
                    for course in courses:
                        course_name = course.get("course_name", "")
                        credit = course.get("credit", 0)
                        semester = course.get("semester", "")
                        total = course.get("total_students", 0) or 0
                        scored = course.get("scored_students", 0) or 0
                        avg_score = course.get("avg_score")
                        min_score = course.get("min_score")
                        max_score = course.get("max_score")
                        excellent = course.get("excellent_count", 0) or 0
                        pass_count = course.get("pass_count", 0) or 0
                        fail = course.get("fail_count", 0) or 0
                        
                        course_info = f"\n• {course_name}（{credit}学分"
                        if semester:
                            course_info += f"，{semester}"
                        course_info += f"）"
                        course_info += f"\n  选课人数：{total}人"
                        if scored > 0:
                            course_info += f"，已有成绩：{scored}人"
                            if avg_score is not None:
                                course_info += f"\n  平均分：{avg_score:.1f}分"
                                if min_score is not None and max_score is not None:
                                    course_info += f"，最高分：{max_score}分，最低分：{min_score}分"
                            if scored > 0:
                                pass_rate = ((excellent + pass_count) / scored * 100) if scored > 0 else 0
                                course_info += f"\n  成绩分布：优秀({excellent}人)，及格({pass_count}人)，不及格({fail}人)，及格率：{pass_rate:.1f}%"
                        else:
                            course_info += "（暂无成绩）"
                        
                        summary.append(course_info)
                
                # 获取需要关注的课程（及格率低于70%或平均分低于70分）
                cur.execute(
                    """
                    SELECT
                        c.course_name,
                        COUNT(s.score_id) AS scored_count,
                        AVG(s.score) AS avg_score,
                        SUM(CASE WHEN s.score >= 60 THEN 1 ELSE 0 END) AS pass_count
                    FROM courses c
                    LEFT JOIN course_selection cs ON c.course_id = cs.course_id
                    LEFT JOIN scores s ON cs.selection_id = s.selection_id AND s.score IS NOT NULL
                    WHERE c.teacher_id = %s
                    GROUP BY c.course_id, c.course_name
                    HAVING scored_count > 0 AND (
                        (pass_count / scored_count < 0.7) OR 
                        (AVG(s.score) < 70)
                    )
                    ORDER BY avg_score ASC
                    """,
                    (teacher_id,),
                )
                concern_courses = cur.fetchall()
                if concern_courses:
                    summary.append(f"\n【需要关注的课程】（及格率低于70%或平均分低于70分）")
                    for course in concern_courses:
                        course_name = course.get("course_name", "")
                        avg_score = course.get("avg_score")
                        scored = course.get("scored_count", 0) or 0
                        pass_count = course.get("pass_count", 0) or 0
                        pass_rate = (pass_count / scored * 100) if scored > 0 else 0
                        summary.append(f"• {course_name}：平均分{avg_score:.1f}分，及格率{pass_rate:.1f}%")
                
                return "\n".join(summary)

            if role == "admin":
                # 管理员：提供整个数据库的统计信息
                summary = ["【系统管理员 - 数据库全览】"]
                
                # 1. 学生统计
                cur.execute("""
                    SELECT 
                        COUNT(*) AS total_students,
                        COUNT(DISTINCT major) AS major_count,
                        AVG(gpa) AS avg_gpa,
                        COUNT(CASE WHEN grade = 1 THEN 1 END) AS grade1,
                        COUNT(CASE WHEN grade = 2 THEN 1 END) AS grade2,
                        COUNT(CASE WHEN grade = 3 THEN 1 END) AS grade3,
                        COUNT(CASE WHEN grade = 4 THEN 1 END) AS grade4
                    FROM students
                """)
                student_stats = cur.fetchone()
                if student_stats:
                    total_students = student_stats.get("total_students", 0) or 0
                    major_count = student_stats.get("major_count", 0) or 0
                    avg_gpa = student_stats.get("avg_gpa")
                    summary.append(f"学生总数：{total_students}人，专业数：{major_count}个")
                    if avg_gpa is not None:
                        summary.append(f"平均GPA：{avg_gpa:.2f}")
                    grade_info = []
                    for g, label in [(1, "大一"), (2, "大二"), (3, "大三"), (4, "大四")]:
                        count = student_stats.get(f"grade{g}", 0) or 0
                        if count > 0:
                            grade_info.append(f"{label}{count}人")
                    if grade_info:
                        summary.append(f"年级分布：{', '.join(grade_info)}")
                
                # 专业分布（前5个）
                cur.execute("""
                    SELECT major, COUNT(*) AS count
                    FROM students
                    WHERE major IS NOT NULL AND major != ''
                    GROUP BY major
                    ORDER BY count DESC
                    LIMIT 5
                """)
                majors = cur.fetchall()
                if majors:
                    major_list = [f"{row['major']}({row['count']}人)" for row in majors]
                    summary.append(f"主要专业：{', '.join(major_list)}")
                
                # 2. 教师统计
                cur.execute("""
                    SELECT 
                        COUNT(*) AS total_teachers,
                        COUNT(DISTINCT department) AS dept_count
                    FROM teachers
                """)
                teacher_stats = cur.fetchone()
                if teacher_stats:
                    total_teachers = teacher_stats.get("total_teachers", 0) or 0
                    dept_count = teacher_stats.get("dept_count", 0) or 0
                    summary.append(f"教师总数：{total_teachers}人，部门数：{dept_count}个")
                
                # 部门分布（前5个）
                cur.execute("""
                    SELECT department, COUNT(*) AS count
                    FROM teachers
                    WHERE department IS NOT NULL AND department != ''
                    GROUP BY department
                    ORDER BY count DESC
                    LIMIT 5
                """)
                depts = cur.fetchall()
                if depts:
                    dept_list = [f"{row['department']}({row['count']}人)" for row in depts]
                    summary.append(f"主要部门：{', '.join(dept_list)}")
                
                # 3. 课程统计
                cur.execute("""
                    SELECT 
                        COUNT(*) AS total_courses,
                        SUM(credit) AS total_credits,
                        COUNT(DISTINCT semester) AS semester_count
                    FROM courses
                """)
                course_stats = cur.fetchone()
                if course_stats:
                    total_courses = course_stats.get("total_courses", 0) or 0
                    total_credits = course_stats.get("total_credits", 0) or 0
                    semester_count = course_stats.get("semester_count", 0) or 0
                    summary.append(f"课程总数：{total_courses}门，总学分：{total_credits}，学期数：{semester_count}个")
                
                # 4. 成绩统计
                cur.execute("""
                    SELECT 
                        COUNT(*) AS total_scores,
                        AVG(score) AS avg_score,
                        MIN(score) AS min_score,
                        MAX(score) AS max_score,
                        COUNT(CASE WHEN score >= 90 THEN 1 END) AS excellent,
                        COUNT(CASE WHEN score >= 60 AND score < 90 THEN 1 END) AS pass,
                        COUNT(CASE WHEN score < 60 THEN 1 END) AS fail
                    FROM scores
                    WHERE score IS NOT NULL
                """)
                score_stats = cur.fetchone()
                if score_stats:
                    total_scores = score_stats.get("total_scores", 0) or 0
                    if total_scores > 0:
                        avg_score = score_stats.get("avg_score")
                        min_score = score_stats.get("min_score")
                        max_score = score_stats.get("max_score")
                        excellent = score_stats.get("excellent", 0) or 0
                        pass_count = score_stats.get("pass", 0) or 0
                        fail = score_stats.get("fail", 0) or 0
                        summary.append(f"成绩记录：{total_scores}条")
                        if avg_score is not None:
                            summary.append(f"平均分：{avg_score:.1f}分，最高分：{max_score}分，最低分：{min_score}分")
                        summary.append(f"优秀(≥90)：{excellent}人，及格(60-89)：{pass_count}人，不及格(<60)：{fail}人")
                
                # 5. 选课情况
                cur.execute("""
                    SELECT 
                        COUNT(DISTINCT student_id) AS students_with_scores,
                        COUNT(DISTINCT course_id) AS courses_with_scores
                    FROM scores
                """)
                enrollment_stats = cur.fetchone()
                if enrollment_stats:
                    students_with_scores = enrollment_stats.get("students_with_scores", 0) or 0
                    courses_with_scores = enrollment_stats.get("courses_with_scores", 0) or 0
                    summary.append(f"选课情况：{students_with_scores}名学生有成绩记录，{courses_with_scores}门课程有成绩")
                
                # 6. 具体信息列表（供大模型查询使用）
                summary.append("\n【具体信息列表】")
                
                # 所有教师信息
                cur.execute("""
                    SELECT name, department, title, research, phone, email
                    FROM teachers
                    ORDER BY teacher_id
                """)
                teachers = cur.fetchall()
                if teachers:
                    teacher_list = []
                    for t in teachers:
                        info = f"姓名：{t.get('name', '未知')}"
                        if t.get('department'):
                            info += f"，部门：{t['department']}"
                        if t.get('title'):
                            info += f"，职称：{t['title']}"
                        if t.get('research'):
                            info += f"，研究方向：{t['research']}"
                        teacher_list.append(info)
                    summary.append(f"教师列表（共{len(teacher_list)}人）：\n" + "\n".join(teacher_list))
                
                # 所有学生信息
                cur.execute("""
                    SELECT name, major, grade, class_name, gpa, phone, email
                    FROM students
                    ORDER BY student_id
                """)
                students = cur.fetchall()
                if students:
                    student_list = []
                    for s in students:
                        info = f"姓名：{s.get('name', '未知')}"
                        if s.get('major'):
                            info += f"，专业：{s['major']}"
                        if s.get('grade'):
                            info += f"，年级：{s['grade']}"
                        if s.get('class_name'):
                            info += f"，班级：{s['class_name']}"
                        if s.get('gpa') is not None:
                            info += f"，GPA：{s['gpa']}"
                        student_list.append(info)
                    summary.append(f"\n学生列表（共{len(student_list)}人）：\n" + "\n".join(student_list))
                
                # 所有课程信息
                cur.execute("""
                    SELECT c.course_name, c.credit, c.semester, t.name AS teacher_name, t.department
                    FROM courses c
                    LEFT JOIN teachers t ON c.teacher_id = t.teacher_id
                    ORDER BY c.course_id
                """)
                courses = cur.fetchall()
                if courses:
                    course_list = []
                    for c in courses:
                        info = f"课程名：{c.get('course_name', '未知')}"
                        if c.get('credit'):
                            info += f"，学分：{c['credit']}"
                        if c.get('semester'):
                            info += f"，学期：{c['semester']}"
                        if c.get('teacher_name'):
                            info += f"，授课教师：{c['teacher_name']}"
                        if c.get('department'):
                            info += f"（{c['department']}）"
                        course_list.append(info)
                    summary.append(f"\n课程列表（共{len(course_list)}门）：\n" + "\n".join(course_list))
                
                # 成绩信息（前20条，作为示例）
                cur.execute("""
                    SELECT s.name AS student_name, c.course_name, sc.score, sc.exam_date
                    FROM scores sc
                    JOIN course_selection cs ON sc.selection_id = cs.selection_id
                    JOIN students s ON cs.student_id = s.student_id
                    JOIN courses c ON cs.course_id = c.course_id
                    WHERE sc.score IS NOT NULL
                    ORDER BY sc.exam_date DESC, sc.score DESC
                    LIMIT 20
                """)
                scores = cur.fetchall()
                if scores:
                    score_list = []
                    for sc in scores:
                        info = f"{sc.get('student_name', '未知')} - {sc.get('course_name', '未知')}：{sc.get('score')}分"
                        if sc.get('exam_date'):
                            info += f"（{sc['exam_date']}）"
                        score_list.append(info)
                    summary.append(f"\n成绩记录示例（最近20条）：\n" + "\n".join(score_list))
                
                return "\n".join(summary)
    except Exception as exc:
        app.logger.exception("构建用户背景失败：%s", exc)

    return ""

# ---------- 登录与用户 ----------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")

    if not username or not password or not role:
        return jsonify({"status": "error", "msg": "用户名、密码和角色不能为空"})

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND role=%s", (username, role))
        row = cur.fetchone()

    if row is None:
        # 检查用户是否存在（但角色不匹配）
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT username, role FROM users WHERE username=%s", (username,))
            user = cur.fetchone()
            if user:
                return jsonify({
                    "status": "error", 
                    "msg": f"角色不匹配。用户 '{username}' 的角色是 '{user['role']}'，不是 '{role}'"
                })
        return jsonify({"status": "error", "msg": "用户不存在"})

    # 检查密码格式并验证
    stored_password = row["password"]
    is_werkzeug_hash = stored_password.startswith('pbkdf2:sha256:')
    
    password_valid = False
    
    if is_werkzeug_hash:
        # Werkzeug 格式的密码哈希
        password_valid = check_password_hash(stored_password, password)
    else:
        # 可能是 MD5 或其他格式的哈希
        # 尝试 MD5 验证
        if len(stored_password) == 32:  # MD5 哈希通常是 32 个字符
            md5_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
            password_valid = (md5_hash.lower() == stored_password.lower())
        elif len(stored_password) == 40:  # SHA1 哈希通常是 40 个字符
            sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest()
            password_valid = (sha1_hash.lower() == stored_password.lower())
        elif len(stored_password) == 64:  # SHA256 哈希通常是 64 个字符
            sha256_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            password_valid = (sha256_hash.lower() == stored_password.lower())
        else:
            # 尝试直接比较（如果是明文，虽然不推荐）
            password_valid = (stored_password == password)
    
    if not password_valid:
        return jsonify({"status": "error", "msg": "密码错误"})

    return jsonify({
        "status": "ok",
        "user_id": row["user_id"],
        "role": row["role"],
        "real_name": row.get("name") or row["username"],
        "token": f"TOKEN-{row['user_id']}"
    })

# ---------- 用户管理 ----------

@app.route("/api/users", methods=["GET"])
def list_users():
    """查询用户列表"""
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword", "").strip()
    user_id = request.args.get("user_id", "").strip()
    username = request.args.get("username", "").strip()
    role = request.args.get("role", "").strip()

    where = []
    params = []
    
    # 如果提供了user_id，精确匹配
    if user_id:
        try:
            where.append("user_id = %s")
            params.append(int(user_id))
        except ValueError:
            pass
    
    # 如果提供了username，模糊匹配
    if username:
        where.append("username LIKE %s")
        params.append(f"%{username}%")
    
    # 如果提供了role，精确匹配
    if role:
        where.append("role = %s")
        params.append(role)
    
    # 如果只提供了keyword（通用搜索），搜索用户名、用户ID
    if keyword and not (user_id or username or role):
        try:
            # 尝试将keyword解析为数字（用户ID）
            user_id_int = int(keyword)
            where.append("(user_id = %s OR username LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([user_id_int, kw])
        except ValueError:
            # 不是数字，只搜索用户名
            where.append("username LIKE %s")
            kw = f"%{keyword}%"
            params.append(kw)

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as total FROM users {where_sql}", params)
        total = cur.fetchone()['total']

        cur.execute(
            f"""
            SELECT user_id, username, role, created_at, last_login
            FROM users
            {where_sql}
            ORDER BY user_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    users = [dict(r) for r in rows]
    return jsonify({
        "status": "ok",
        "data": users,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@app.route("/api/users/<int:user_id>/password", methods=["PUT"])
def change_user_password(user_id):
    """修改用户密码"""
    data = request.json or {}
    old_password = data.get("old_password", "").strip()
    new_password = data.get("new_password", "").strip()

    if not old_password or not new_password:
        return jsonify({"status": "error", "msg": "原密码和新密码不能为空"}), 400

    if len(new_password) < 6:
        return jsonify({"status": "error", "msg": "新密码长度至少为6位"}), 400

    with get_conn() as conn:
        cur = conn.cursor()
        # 查询用户
        cur.execute("SELECT password FROM users WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        
        if row is None:
            return jsonify({"status": "error", "msg": "用户不存在"}), 404
        
        stored_password = row["password"]
        is_werkzeug_hash = stored_password.startswith('pbkdf2:sha256:')
        
        # 验证原密码
        password_valid = False
        
        if is_werkzeug_hash:
            # Werkzeug 格式的密码哈希
            password_valid = check_password_hash(stored_password, old_password)
        else:
            # 可能是 MD5 或其他格式的哈希
            if len(stored_password) == 32:  # MD5 哈希通常是 32 个字符
                md5_hash = hashlib.md5(old_password.encode('utf-8')).hexdigest()
                password_valid = (md5_hash.lower() == stored_password.lower())
            elif len(stored_password) == 40:  # SHA1 哈希通常是 40 个字符
                sha1_hash = hashlib.sha1(old_password.encode('utf-8')).hexdigest()
                password_valid = (sha1_hash.lower() == stored_password.lower())
            elif len(stored_password) == 64:  # SHA256 哈希通常是 64 个字符
                sha256_hash = hashlib.sha256(old_password.encode('utf-8')).hexdigest()
                password_valid = (sha256_hash.lower() == stored_password.lower())
            else:
                # 尝试直接比较（如果是明文，虽然不推荐）
                password_valid = (stored_password == old_password)
        
        if not password_valid:
            return jsonify({"status": "error", "msg": "原密码错误"}), 400
        
        # 使用SHA-256哈希新密码
        new_password_hash = hashlib.sha256(new_password.encode('utf-8')).hexdigest()
        
        # 更新密码
        cur.execute("UPDATE users SET password=%s WHERE user_id=%s", (new_password_hash, user_id))
        
    return jsonify({"status": "ok", "msg": "密码修改成功"})

# ---------- 学生 CRUD + 搜索 + 分页 ----------

@app.route("/api/students", methods=["GET"])
def list_students():
    # 参数：page, page_size, keyword, student_id, name, major, class_name
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword", "").strip()
    student_id = request.args.get("student_id", "").strip()
    name = request.args.get("name", "").strip()
    major = request.args.get("major", "").strip()
    class_name = request.args.get("class_name", "").strip()

    where = []
    params = []
    
    # 如果提供了student_id，精确匹配
    if student_id:
        try:
            where.append("student_id = %s")
            params.append(int(student_id))
        except ValueError:
            pass
    
    # 如果提供了name，模糊匹配
    if name:
        where.append("name LIKE %s")
        params.append(f"%{name}%")
    
    # 如果提供了major，模糊匹配
    if major:
        where.append("major LIKE %s")
        params.append(f"%{major}%")
    
    # 如果提供了class_name，精确匹配
    if class_name:
        where.append("class_name = %s")
        params.append(class_name)
    
    # 如果只提供了keyword（通用搜索），搜索姓名、学号、专业
    if keyword and not (student_id or name or major or class_name):
        try:
            # 尝试将keyword解析为数字（学号）
            student_id_int = int(keyword)
            where.append("(student_id = %s OR name LIKE %s OR major LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([student_id_int, kw, kw])
        except ValueError:
            # 不是数字，只搜索姓名和专业
            where.append("(name LIKE %s OR major LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as total FROM students {where_sql}", params)
        total = cur.fetchone()['total']

        cur.execute(
            f"""
            SELECT * FROM students
            {where_sql}
            ORDER BY student_id DESC
            LIMIT %s OFFSET %s
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
    """新增学生，自动创建users表记录"""
    from werkzeug.security import generate_password_hash
    import hashlib
    
    data = request.json or {}
    name = data.get("name", "").strip()
    gender = data.get("gender", "male")
    age = data.get("age")
    major = data.get("major", "").strip()
    grade = data.get("grade")
    class_name = data.get("class_name", "").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    gpa = data.get("gpa")
    username = data.get("username", "").strip()  # 可选，如果不提供则自动生成
    password = data.get("password", "").strip()  # 可选，如果不提供则使用默认密码

    if not name:
        return jsonify({"status": "error", "msg": "姓名不能为空"}), 400

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 生成用户名（如果未提供）
            if not username:
                # 使用姓名拼音首字母 + 时间戳后6位，或使用student_id（但需要先插入）
                # 简单方案：使用姓名 + 随机数
                import random
                base_username = name.lower().replace(" ", "")[:10]  # 取姓名前10个字符
                username = f"{base_username}{random.randint(1000, 9999)}"
            
            # 检查用户名是否已存在
            cur.execute("SELECT user_id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                # 如果用户名已存在，添加随机后缀
                import random
                username = f"{username}{random.randint(100, 999)}"
            
            # 生成密码（如果未提供，使用默认密码"123456"）
            if not password:
                password = "123456"
            
            # 使用MD5哈希密码（与现有系统保持一致）
            password_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
            
            # 创建users表记录
            cur.execute("""
            INSERT INTO users (username, password, role)
            VALUES (%s, %s, 'student')
            """, (username, password_hash))
            user_id = cur.lastrowid
            
            # 创建students表记录
            cur.execute("""
            INSERT INTO students (user_id, name, gender, age, major, grade, class_name, phone, email, gpa)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, name, gender, age, major, grade, class_name, phone, email, gpa))
            student_id = cur.lastrowid
            
            # 记录操作日志
            token = request.headers.get("X-Token", "")
            if token and token.startswith("TOKEN-"):
                try:
                    admin_user_id = int(token.replace("TOKEN-", ""))
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        admin_user_id,
                        "CREATE",
                        "students",
                        student_id,
                        f"新增学生: {name} (用户名: {username})"
                    ))
                except:
                    pass
            
            conn.commit()
        
        return jsonify({
            "status": "ok",
            "id": student_id,
            "user_id": user_id,
            "username": username,
            "password": password  # 返回初始密码，方便管理员告知学生
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": f"创建失败：{str(e)}"}), 500

@app.route("/api/students/<int:sid>", methods=["PUT"])
def update_student(sid):
    """修改学生信息（管理员可以修改所有字段）"""
    try:
        data = request.json or {}
        
        # 获取当前用户ID和角色（从 token 中提取）
        token = request.headers.get("X-Token", "")
        user_id = None
        user_role = None
        if token and token.startswith("TOKEN-"):
            try:
                user_id = int(token.replace("TOKEN-", ""))
                user = _get_user_from_token(token)
                if user:
                    user_role = user.get("role")
            except:
                pass
        
        # 只有管理员可以修改所有字段，其他角色只能修改phone和email
        is_admin = (user_role == "admin")
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 检查学生是否存在，获取所有旧数据
            cur.execute("""
            SELECT name, gender, age, major, grade, class_name, phone, email, gpa
            FROM students WHERE student_id=%s
            """, (sid,))
            old_data = cur.fetchone()
            if not old_data:
                return jsonify({"status": "error", "msg": "学生不存在"}), 404
            
            old_dict = dict(old_data)
            
            # 构建更新字段和值
            update_fields = []
            update_values = []
            changes = []
            
            # 管理员可以修改所有字段
            if is_admin:
                allowed_fields = ["name", "gender", "age", "major", "grade", "class_name", "phone", "email", "gpa"]
                for field in allowed_fields:
                    if field in data:
                        new_val = data.get(field)
                        old_val = old_dict.get(field)
                        # 处理None值
                        if new_val is None:
                            new_val = None
                        elif isinstance(new_val, str):
                            new_val = new_val.strip()
                        
                        if old_val != new_val:
                            update_fields.append(f"{field}=%s")
                            update_values.append(new_val)
                            changes.append(f"{field}: '{old_val or ''}' -> '{new_val or ''}'")
            else:
                # 非管理员只能修改phone和email
                for field in ["phone", "email"]:
                    if field in data:
                        new_val = data.get(field, "").strip()
                        old_val = old_dict.get(field, "")
                        if old_val != new_val:
                            update_fields.append(f"{field}=%s")
                            update_values.append(new_val)
                            changes.append(f"{field}: '{old_val}' -> '{new_val}'")
            
            # 如果有更新，执行SQL
            if update_fields:
                update_values.append(sid)
                sql = f"UPDATE students SET {', '.join(update_fields)} WHERE student_id=%s"
                cur.execute(sql, update_values)
                
                # 记录 audit_log
                if user_id:
                    details = "; ".join(changes) if changes else "无变更"
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        "UPDATE",
                        "students",
                        sid,
                        f"更新学生信息: {details}"
                    ))
                conn.commit()
            else:
                # 没有实际更新
                conn.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"更新失败：{str(e)}"}), 500

@app.route("/api/students/<int:sid>", methods=["DELETE"])
def delete_student(sid):
    """删除学生（Cascade删除scores，同时删除users）"""
    # 检查权限：只有管理员可以删除
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以删除学生"}), 403
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 先获取学生信息用于日志
            cur.execute("SELECT name, user_id FROM students WHERE student_id=%s", (sid,))
            student = cur.fetchone()
            if not student:
                return jsonify({"status": "error", "msg": "学生不存在"}), 404
            
            student_name = student.get("name", "")
            user_id_to_delete = student.get("user_id")
            
            # 删除students记录（会自动CASCADE删除scores，因为scores.student_id有外键约束）
            cur.execute("DELETE FROM students WHERE student_id=%s", (sid,))
            
            # 删除对应的users记录（students.user_id有外键指向users，但删除students不会自动删除users）
            # 需要手动删除users记录
            if user_id_to_delete:
                cur.execute("DELETE FROM users WHERE user_id=%s", (user_id_to_delete,))
            
            # 记录操作日志
            if user.get("user_id"):
                cur.execute("""
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "DELETE",
                    "students",
                    sid,
                    f"删除学生: {student_name} (user_id: {user_id_to_delete})"
                ))
            
            conn.commit()
        
        return jsonify({"status": "ok", "msg": "删除成功"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"删除失败：{str(e)}"}), 500

# ---------- 教师 / 课程 / 成绩 CRUD（简单版，与学生类似） ----------

@app.route("/api/teachers", methods=["GET"])
def list_teachers():
    """获取教师列表，支持搜索和分页"""
    # 参数：page, page_size, keyword, teacher_id, name, department
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword", "").strip()
    teacher_id = request.args.get("teacher_id", "").strip()
    name = request.args.get("name", "").strip()
    department = request.args.get("department", "").strip()

    where = []
    params = []
    
    # 如果提供了teacher_id，精确匹配
    if teacher_id:
        try:
            where.append("teacher_id = %s")
            params.append(int(teacher_id))
        except ValueError:
            pass
    
    # 如果提供了name，模糊匹配
    if name:
        where.append("name LIKE %s")
        params.append(f"%{name}%")
    
    # 如果提供了department，模糊匹配
    if department:
        where.append("department LIKE %s")
        params.append(f"%{department}%")
    
    # 如果只提供了keyword（通用搜索），搜索姓名、工号、学院
    if keyword and not (teacher_id or name or department):
        try:
            # 尝试将keyword解析为数字（工号）
            teacher_id_int = int(keyword)
            where.append("(teacher_id = %s OR name LIKE %s OR department LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([teacher_id_int, kw, kw])
        except ValueError:
            # 不是数字，只搜索姓名和学院
            where.append("(name LIKE %s OR department LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as total FROM teachers {where_sql}", params)
        total = cur.fetchone()['total']

        cur.execute(
            f"""
            SELECT * FROM teachers
            {where_sql}
            ORDER BY teacher_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    teachers = [dict(r) for r in rows]
    return jsonify({
        "status": "ok",
        "data": teachers,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@app.route("/api/teachers", methods=["POST"])
def create_teacher():
    """新增教师，自动创建users表记录"""
    import hashlib
    
    data = request.json or {}
    name = data.get("name", "").strip()
    department = data.get("department", "").strip()
    title = data.get("title", "").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    research = data.get("research", "").strip()
    username = data.get("username", "").strip()  # 可选，如果不提供则自动生成
    password = data.get("password", "").strip()  # 可选，如果不提供则使用默认密码

    if not name:
        return jsonify({"status": "error", "msg": "姓名不能为空"}), 400

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 生成用户名（如果未提供）
            if not username:
                # 使用姓名拼音首字母 + 随机数
                import random
                base_username = name.lower().replace(" ", "")[:10]  # 取姓名前10个字符
                username = f"{base_username}{random.randint(1000, 9999)}"
            
            # 检查用户名是否已存在
            cur.execute("SELECT user_id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                # 如果用户名已存在，添加随机后缀
                import random
                username = f"{username}{random.randint(100, 999)}"
            
            # 生成密码（如果未提供，使用默认密码"123456"）
            if not password:
                password = "123456"
            
            # 使用MD5哈希密码（与现有系统保持一致）
            password_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
            
            # 创建users表记录
            cur.execute("""
            INSERT INTO users (username, password, role)
            VALUES (%s, %s, 'teacher')
            """, (username, password_hash))
            user_id = cur.lastrowid
            
            # 创建teachers表记录
            cur.execute("""
            INSERT INTO teachers (user_id, name, department, title, phone, email, research)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, name, department, title, phone, email, research))
            teacher_id = cur.lastrowid
            
            # 记录操作日志
            token = request.headers.get("X-Token", "")
            if token and token.startswith("TOKEN-"):
                try:
                    admin_user_id = int(token.replace("TOKEN-", ""))
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        admin_user_id,
                        "CREATE",
                        "teachers",
                        teacher_id,
                        f"新增教师: {name} (用户名: {username})"
                    ))
                except:
                    pass
            
            conn.commit()
        
        return jsonify({
            "status": "ok",
            "id": teacher_id,
            "user_id": user_id,
            "username": username,
            "password": password  # 返回初始密码，方便管理员告知教师
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": f"创建失败：{str(e)}"}), 500

@app.route("/api/teachers/<int:tid>", methods=["PUT"])
def update_teacher(tid):
    """修改教师信息（管理员可以修改所有字段）"""
    try:
        data = request.json or {}
        
        # 获取当前用户ID和角色（从 token 中提取）
        token = request.headers.get("X-Token", "")
        user_id = None
        user_role = None
        if token and token.startswith("TOKEN-"):
            try:
                user_id = int(token.replace("TOKEN-", ""))
                user = _get_user_from_token(token)
                if user:
                    user_role = user.get("role")
            except:
                pass
        
        # 只有管理员可以修改所有字段，教师只能修改自己的phone、email、research
        is_admin = (user_role == "admin")
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 检查教师是否存在，获取所有旧数据
            cur.execute("""
            SELECT name, department, title, phone, email, research, user_id
            FROM teachers WHERE teacher_id=%s
            """, (tid,))
            old_data = cur.fetchone()
            if not old_data:
                return jsonify({"status": "error", "msg": "教师不存在"}), 404
            
            old_dict = dict(old_data)
            
            # 如果不是管理员，检查是否是教师本人
            if not is_admin:
                if user_role != "teacher" or user_id != old_dict.get("user_id"):
                    return jsonify({"status": "error", "msg": "无权修改该教师信息"}), 403
            
            # 构建更新字段和值
            update_fields = []
            update_values = []
            changes = []
            
            # 管理员可以修改所有字段
            if is_admin:
                allowed_fields = ["name", "department", "title", "phone", "email", "research"]
                for field in allowed_fields:
                    if field in data:
                        new_val = data.get(field)
                        old_val = old_dict.get(field)
                        # 处理None值
                        if new_val is None:
                            new_val = None
                        elif isinstance(new_val, str):
                            new_val = new_val.strip()
                        
                        if old_val != new_val:
                            update_fields.append(f"{field}=%s")
                            update_values.append(new_val)
                            changes.append(f"{field}: '{old_val or ''}' -> '{new_val or ''}'")
            else:
                # 教师只能修改phone、email、research
                for field in ["phone", "email", "research"]:
                    if field in data:
                        new_val = data.get(field, "").strip()
                        old_val = old_dict.get(field, "")
                        if old_val != new_val:
                            update_fields.append(f"{field}=%s")
                            update_values.append(new_val)
                            changes.append(f"{field}: '{old_val}' -> '{new_val}'")
            
            # 如果有更新，执行SQL
            if update_fields:
                update_values.append(tid)
                sql = f"UPDATE teachers SET {', '.join(update_fields)} WHERE teacher_id=%s"
                cur.execute(sql, update_values)
                
                # 记录 audit_log
                if user_id:
                    details = "; ".join(changes) if changes else "无变更"
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        "UPDATE",
                        "teachers",
                        tid,
                        f"更新教师信息: {details}"
                    ))
                conn.commit()
            else:
                # 没有实际更新
                conn.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"更新失败：{str(e)}"}), 500

@app.route("/api/teachers/<int:tid>", methods=["DELETE"])
def delete_teacher(tid):
    """删除教师（设置courses.teacher_id = NULL，同时删除users）"""
    # 检查权限：只有管理员可以删除
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以删除教师"}), 403
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 先获取教师信息用于日志
            cur.execute("SELECT name, user_id FROM teachers WHERE teacher_id=%s", (tid,))
            teacher = cur.fetchone()
            if not teacher:
                return jsonify({"status": "error", "msg": "教师不存在"}), 404
            
            teacher_name = teacher.get("name", "")
            user_id_to_delete = teacher.get("user_id")
            
            # 先设置courses.teacher_id = NULL（避免外键约束问题）
            cur.execute("UPDATE courses SET teacher_id = NULL WHERE teacher_id=%s", (tid,))
            
            # 删除teachers记录
            cur.execute("DELETE FROM teachers WHERE teacher_id=%s", (tid,))
            
            # 删除对应的users记录
            if user_id_to_delete:
                cur.execute("DELETE FROM users WHERE user_id=%s", (user_id_to_delete,))
            
            # 记录操作日志
            if user.get("user_id"):
                cur.execute("""
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "DELETE",
                    "teachers",
                    tid,
                    f"删除教师: {teacher_name} (user_id: {user_id_to_delete})"
                ))
            
            conn.commit()
        
        return jsonify({"status": "ok", "msg": "删除成功"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"删除失败：{str(e)}"}), 500


@app.route("/api/teacher/profile", methods=["GET"])
def get_teacher_profile():
    try:
        token = request.headers.get("X-Token", "")
        user = _get_user_from_token(token)
        if not user:
            return jsonify({"status": "error", "msg": "请先登录"}), 401
        if user["role"] != "teacher":
            return jsonify({"status": "error", "msg": "仅教师可以访问"}), 403

        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT t.teacher_id, t.user_id, t.name, t.department, t.title,
                       t.phone, t.email, t.research, u.username
                FROM teachers t
                JOIN users u ON t.user_id = u.user_id
                WHERE t.user_id=%s
                """,
                (user["user_id"],),
            )
            row = cur.fetchone()

        if not row:
            return jsonify({"status": "error", "msg": "未找到教师档案"}), 404

        return jsonify({"status": "ok", "data": row})
    except Exception as e:
        import traceback
        print(f"get_teacher_profile 错误: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "error", "msg": f"获取教师信息失败：{str(e)}"}), 500


@app.route("/api/teacher/profile", methods=["PUT"])
def update_teacher_profile():
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user["role"] != "teacher":
        return jsonify({"status": "error", "msg": "仅教师可以修改"}), 403

    data = request.json or {}

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT teacher_id, phone, email, research
            FROM teachers
            WHERE user_id=%s
            """,
            (user["user_id"],),
        )
        old = cur.fetchone()
        if not old:
            return jsonify({"status": "error", "msg": "未找到教师档案"}), 404

        phone = data.get("phone", old.get("phone"))
        email = data.get("email", old.get("email"))
        research = data.get("research", old.get("research"))

        cur.execute(
            """
            UPDATE teachers
            SET phone=%s,
                email=%s,
                research=%s
            WHERE user_id=%s
            """,
            (phone, email, research, user["user_id"]),
        )

        changes = []
        for field, new_val in {"phone": phone, "email": email, "research": research}.items():
            if old.get(field) != new_val:
                changes.append(f"{field}: '{old.get(field) or ''}' -> '{new_val or ''}'")

        if changes:
            cur.execute(
                """
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    user["user_id"],
                    "UPDATE",
                    "teachers",
                    old["teacher_id"],
                    f"教师修改个人信息: {'; '.join(changes)}",
                ),
            )

    return jsonify({"status": "ok"})


@app.route("/api/teacher/my-courses", methods=["GET"])
def get_teacher_my_courses():
    """获取当前教师教授的课程列表（含选课人数统计）"""
    try:
        token = request.headers.get("X-Token", "")
        user = _get_user_from_token(token)
        if not user:
            return jsonify({"status": "error", "msg": "请先登录"}), 401
        if user["role"] != "teacher":
            return jsonify({"status": "error", "msg": "仅教师可以访问"}), 403

        # 先获取当前教师的teacher_id
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT teacher_id FROM teachers WHERE user_id=%s
                """,
                (user["user_id"],),
            )
            teacher_row = cur.fetchone()
            if not teacher_row:
                return jsonify({"status": "error", "msg": "未找到教师档案"}), 404

            teacher_id = teacher_row["teacher_id"]

            # 查询该教师教授的课程，并统计选课人数
            cur.execute(
                """
                SELECT
                    c.course_id,
                    c.course_name,
                    c.credit,
                    COALESCE(c.semester, '') AS semester,
                    COUNT(DISTINCT cs.selection_id) AS selected_count
                FROM courses c
                LEFT JOIN course_selection cs ON c.course_id = cs.course_id
                WHERE c.teacher_id = %s
                GROUP BY c.course_id, c.course_name, c.credit, c.semester
                ORDER BY c.course_id DESC
                """,
                (teacher_id,),
            )
            rows = cur.fetchall()

        return jsonify({"status": "ok", "data": [dict(r) for r in rows]})
    except Exception as e:
        import traceback
        print(f"get_teacher_my_courses 错误: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "error", "msg": f"获取课程列表失败：{str(e)}"}), 500


@app.route("/api/courses", methods=["GET"])
def list_courses():
    """获取课程列表，支持搜索和分页"""
    # 参数：page, page_size, keyword, course_id, course_name, teacher_name, semester
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword", "").strip()
    course_id = request.args.get("course_id", "").strip()
    course_name = request.args.get("course_name", "").strip()
    teacher_name = request.args.get("teacher_name", "").strip()
    semester = request.args.get("semester", "").strip()

    where = []
    params = []
    
    # 如果提供了course_id，精确匹配
    if course_id:
        try:
            where.append("c.course_id = %s")
            params.append(int(course_id))
        except ValueError:
            pass
    
    # 如果提供了course_name，模糊匹配
    if course_name:
        where.append("c.course_name LIKE %s")
        params.append(f"%{course_name}%")
    
    # 如果提供了teacher_name，模糊匹配
    if teacher_name:
        where.append("t.name LIKE %s")
        params.append(f"%{teacher_name}%")
    
    # 如果提供了semester，精确匹配
    if semester:
        where.append("c.semester = %s")
        params.append(semester)
    
    # 如果只提供了keyword（通用搜索），搜索课程号、课程名、任课教师
    if keyword and not (course_id or course_name or teacher_name):
        try:
            # 尝试将keyword解析为数字（课程号）
            course_id_int = int(keyword)
            where.append("(c.course_id = %s OR c.course_name LIKE %s OR t.name LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([course_id_int, kw, kw])
        except ValueError:
            # 不是数字，只搜索课程名和教师名
            where.append("(c.course_name LIKE %s OR t.name LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT COUNT(*) as total 
        FROM courses c
        LEFT JOIN teachers t ON c.teacher_id = t.teacher_id
        {where_sql}
        """, params)
        total = cur.fetchone()['total']

        cur.execute(
            f"""
            SELECT c.*, t.name AS teacher_name
            FROM courses c
            LEFT JOIN teachers t ON c.teacher_id = t.teacher_id
            {where_sql}
            ORDER BY c.course_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    courses = [dict(r) for r in rows]
    return jsonify({
        "status": "ok",
        "data": courses,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@app.route("/api/courses", methods=["POST"])
def create_course():
    """新增课程"""
    data = request.json or {}
    course_name = data.get("course_name", "").strip()
    teacher_id = data.get("teacher_id")
    credit = data.get("credit")
    semester = data.get("semester", "").strip()

    if not course_name:
        return jsonify({"status": "error", "msg": "课程名不能为空"}), 400

    # 验证teacher_id是否存在（如果提供了）
    if teacher_id:
        try:
            teacher_id = int(teacher_id)
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT teacher_id FROM teachers WHERE teacher_id=%s", (teacher_id,))
                if not cur.fetchone():
                    return jsonify({"status": "error", "msg": "教师不存在"}), 400
        except (ValueError, TypeError):
            return jsonify({"status": "error", "msg": "教师ID格式错误"}), 400

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 创建课程记录
            cur.execute("""
            INSERT INTO courses (course_name, teacher_id, credit, semester)
            VALUES (%s, %s, %s, %s)
            """, (course_name, teacher_id if teacher_id else None, credit, semester))
            course_id = cur.lastrowid
            
            # 记录操作日志
            token = request.headers.get("X-Token", "")
            if token and token.startswith("TOKEN-"):
                try:
                    admin_user_id = int(token.replace("TOKEN-", ""))
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        admin_user_id,
                        "CREATE",
                        "courses",
                        course_id,
                        f"新增课程: {course_name} (教师ID: {teacher_id or '无'}, 学分: {credit or '未设置'}, 学期: {semester or '未设置'})"
                    ))
                except:
                    pass
            
            conn.commit()
        
        return jsonify({
            "status": "ok",
            "id": course_id
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": f"创建失败：{str(e)}"}), 500

@app.route("/api/courses/<int:cid>", methods=["PUT"])
def update_course(cid):
    """修改课程信息"""
    try:
        data = request.json or {}
        
        # 获取当前用户ID和角色（从 token 中提取）
        token = request.headers.get("X-Token", "")
        user_id = None
        user_role = None
        if token and token.startswith("TOKEN-"):
            try:
                user_id = int(token.replace("TOKEN-", ""))
                user = _get_user_from_token(token)
                if user:
                    user_role = user.get("role")
            except:
                pass
        
        # 只有管理员可以修改课程
        if user_role != "admin":
            return jsonify({"status": "error", "msg": "只有管理员可以修改课程"}), 403
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 检查课程是否存在，获取所有旧数据
            cur.execute("""
            SELECT course_name, teacher_id, credit, semester
            FROM courses WHERE course_id=%s
            """, (cid,))
            old_data = cur.fetchone()
            if not old_data:
                return jsonify({"status": "error", "msg": "课程不存在"}), 404
            
            old_dict = dict(old_data)
            
            # 构建更新字段和值
            update_fields = []
            update_values = []
            changes = []
            
            # 管理员可以修改所有字段
            allowed_fields = ["course_name", "teacher_id", "credit", "semester"]
            for field in allowed_fields:
                if field in data:
                    new_val = data.get(field)
                    old_val = old_dict.get(field)
                    
                    # 处理None值和字符串
                    if new_val is None:
                        new_val = None
                    elif isinstance(new_val, str):
                        new_val = new_val.strip() if new_val.strip() else None
                    elif field == "teacher_id":
                        # teacher_id可以是None或整数
                        if new_val == "" or new_val == 0:
                            new_val = None
                        else:
                            try:
                                new_val = int(new_val)
                                # 验证teacher_id是否存在
                                cur.execute("SELECT teacher_id FROM teachers WHERE teacher_id=%s", (new_val,))
                                if not cur.fetchone():
                                    return jsonify({"status": "error", "msg": f"教师ID {new_val} 不存在"}), 400
                            except (ValueError, TypeError):
                                return jsonify({"status": "error", "msg": "教师ID格式错误"}), 400
                    
                    if old_val != new_val:
                        update_fields.append(f"{field}=%s")
                        update_values.append(new_val)
                        changes.append(f"{field}: '{old_val or ''}' -> '{new_val or ''}'")
            
            # 如果有更新，执行SQL
            if update_fields:
                update_values.append(cid)
                sql = f"UPDATE courses SET {', '.join(update_fields)} WHERE course_id=%s"
                cur.execute(sql, update_values)
                
                # 记录 audit_log
                if user_id:
                    details = "; ".join(changes) if changes else "无变更"
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        "UPDATE",
                        "courses",
                        cid,
                        f"更新课程信息: {details}"
                    ))
                conn.commit()
            else:
                # 没有实际更新
                conn.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"更新失败：{str(e)}"}), 500

@app.route("/api/courses/<int:cid>", methods=["DELETE"])
def delete_course(cid):
    """删除课程（Cascade删除scores）"""
    # 检查权限：只有管理员可以删除
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以删除课程"}), 403
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 先获取课程信息用于日志
            cur.execute("SELECT course_name FROM courses WHERE course_id=%s", (cid,))
            course = cur.fetchone()
            if not course:
                return jsonify({"status": "error", "msg": "课程不存在"}), 404
            
            course_name = course.get("course_name", "")
            
            # 删除courses记录（会自动CASCADE删除scores，因为scores.course_id有外键约束）
            cur.execute("DELETE FROM courses WHERE course_id=%s", (cid,))
            
            # 记录操作日志
            if user.get("user_id"):
                cur.execute("""
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "DELETE",
                    "courses",
                    cid,
                    f"删除课程: {course_name} (同时删除所有相关成绩记录)"
                ))
            
            conn.commit()
        
        return jsonify({"status": "ok", "msg": "删除成功"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"删除失败：{str(e)}"}), 500

# ---------- 教室管理 CRUD ----------

@app.route("/api/classrooms", methods=["GET"])
def list_classrooms():
    """获取教室列表，支持搜索和分页"""
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword", "").strip()
    classroom_id = request.args.get("classroom_id", "").strip()
    building = request.args.get("building", "").strip()
    room = request.args.get("room", "").strip()

    where = []
    params = []
    
    # 如果提供了classroom_id，精确匹配
    if classroom_id:
        try:
            where.append("classroom_id = %s")
            params.append(int(classroom_id))
        except ValueError:
            pass
    
    # 如果提供了building，模糊匹配
    if building:
        where.append("building LIKE %s")
        params.append(f"%{building}%")
    
    # 如果提供了room，模糊匹配
    if room:
        where.append("room LIKE %s")
        params.append(f"%{room}%")
    
    # 如果只提供了keyword（通用搜索），搜索教室ID、楼栋、房间号
    if keyword and not (classroom_id or building or room):
        try:
            # 尝试将keyword解析为数字（教室ID）
            classroom_id_int = int(keyword)
            where.append("(classroom_id = %s OR building LIKE %s OR room LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([classroom_id_int, kw, kw])
        except ValueError:
            # 不是数字，只搜索楼栋和房间号
            where.append("(building LIKE %s OR room LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as total FROM classrooms {where_sql}", params)
        total = cur.fetchone()['total']

        cur.execute(
            f"""
            SELECT * FROM classrooms
            {where_sql}
            ORDER BY classroom_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    classrooms = [dict(r) for r in rows]
    return jsonify({
        "status": "ok",
        "data": classrooms,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@app.route("/api/classrooms", methods=["POST"])
def create_classroom():
    """新增教室"""
    # 检查权限：只有管理员可以创建
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以创建教室"}), 403
    
    data = request.json or {}
    building = data.get("building", "").strip()
    room = data.get("room", "").strip()
    capacity = data.get("capacity")

    if not building:
        return jsonify({"status": "error", "msg": "楼栋不能为空"}), 400
    if not room:
        return jsonify({"status": "error", "msg": "房间号不能为空"}), 400
    
    # 验证容量
    if capacity is not None:
        try:
            capacity = int(capacity)
            if capacity <= 0:
                return jsonify({"status": "error", "msg": "容量必须大于0"}), 400
        except (ValueError, TypeError):
            return jsonify({"status": "error", "msg": "容量格式错误"}), 400
    else:
        capacity = 60  # 默认容量

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 检查是否已存在相同的楼栋和房间号
            cur.execute("SELECT classroom_id FROM classrooms WHERE building=%s AND room=%s", (building, room))
            if cur.fetchone():
                return jsonify({"status": "error", "msg": "该教室已存在"}), 400
            
            # 创建教室记录
            cur.execute("""
            INSERT INTO classrooms (building, room, capacity)
            VALUES (%s, %s, %s)
            """, (building, room, capacity))
            classroom_id = cur.lastrowid
            
            # 记录操作日志
            if user.get("user_id"):
                cur.execute("""
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "CREATE",
                    "classrooms",
                    classroom_id,
                    f"新增教室: {building}{room} (容量: {capacity})"
                ))
            
            conn.commit()
        
        return jsonify({
            "status": "ok",
            "id": classroom_id
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": f"创建失败：{str(e)}"}), 500

@app.route("/api/classrooms/<int:cid>", methods=["PUT"])
def update_classroom(cid):
    """修改教室信息"""
    # 检查权限：只有管理员可以修改
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以修改教室"}), 403
    
    data = request.json or {}
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 先获取原记录
            cur.execute("SELECT * FROM classrooms WHERE classroom_id=%s", (cid,))
            old_row = cur.fetchone()
            if not old_row:
                return jsonify({"status": "error", "msg": "教室不存在"}), 404
            
            old_data = dict(old_row)
            
            # 构建更新字段
            update_fields = []
            update_values = []
            changes = []
            user_id = user.get("user_id")
            
            # 可更新字段
            updatable_fields = ["building", "room", "capacity"]
            
            for field in updatable_fields:
                if field in data:
                    new_val = data[field]
                    old_val = old_data.get(field)
                    
                    # 处理不同类型的值
                    if field == "capacity":
                        if new_val is not None:
                            try:
                                new_val = int(new_val)
                                if new_val <= 0:
                                    return jsonify({"status": "error", "msg": "容量必须大于0"}), 400
                            except (ValueError, TypeError):
                                return jsonify({"status": "error", "msg": "容量格式错误"}), 400
                        else:
                            new_val = 60  # 默认容量
                    elif isinstance(new_val, str):
                        new_val = new_val.strip() if new_val.strip() else None
                        if field in ["building", "room"] and not new_val:
                            return jsonify({"status": "error", "msg": f"{field}不能为空"}), 400
                    
                    # 如果是building或room，检查是否与其他教室重复
                    if field in ["building", "room"]:
                        other_building = new_val if field == "building" else old_data.get("building")
                        other_room = new_val if field == "room" else old_data.get("room")
                        cur.execute("SELECT classroom_id FROM classrooms WHERE building=%s AND room=%s AND classroom_id!=%s", 
                                   (other_building, other_room, cid))
                        if cur.fetchone():
                            return jsonify({"status": "error", "msg": "该教室已存在"}), 400
                    
                    if old_val != new_val:
                        update_fields.append(f"{field}=%s")
                        update_values.append(new_val)
                        changes.append(f"{field}: '{old_val or ''}' -> '{new_val or ''}'")
            
            # 如果有更新，执行SQL
            if update_fields:
                update_values.append(cid)
                sql = f"UPDATE classrooms SET {', '.join(update_fields)} WHERE classroom_id=%s"
                cur.execute(sql, update_values)
                
                # 记录 audit_log
                if user_id:
                    details = "; ".join(changes) if changes else "无变更"
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        "UPDATE",
                        "classrooms",
                        cid,
                        f"更新教室信息: {details}"
                    ))
                conn.commit()
            else:
                # 没有实际更新
                conn.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"更新失败：{str(e)}"}), 500

@app.route("/api/classrooms/<int:cid>", methods=["DELETE"])
def delete_classroom(cid):
    """删除教室"""
    # 检查权限：只有管理员可以删除
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以删除教室"}), 403
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 先获取教室信息用于日志
            cur.execute("SELECT building, room FROM classrooms WHERE classroom_id=%s", (cid,))
            classroom = cur.fetchone()
            if not classroom:
                return jsonify({"status": "error", "msg": "教室不存在"}), 404
            
            building = classroom.get("building", "")
            room = classroom.get("room", "")
            classroom_name = f"{building}{room}"
            
            # 检查是否被课程表使用
            cur.execute("SELECT COUNT(*) as cnt FROM course_schedule WHERE classroom_id=%s", (cid,))
            usage_count = cur.fetchone()['cnt']
            if usage_count > 0:
                return jsonify({"status": "error", "msg": f"该教室正在被{usage_count}个课程使用，无法删除"}), 400
            
            # 删除教室记录
            cur.execute("DELETE FROM classrooms WHERE classroom_id=%s", (cid,))
            
            # 记录操作日志
            if user.get("user_id"):
                cur.execute("""
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "DELETE",
                    "classrooms",
                    cid,
                    f"删除教室: {classroom_name}"
                ))
            
            conn.commit()
        
        return jsonify({"status": "ok", "msg": "删除成功"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"删除失败：{str(e)}"}), 500

# ---------- 课程安排管理 CRUD ----------

@app.route("/api/course-schedules", methods=["GET"])
def list_course_schedules():
    """获取课程安排列表，支持搜索和分页"""
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    keyword = request.args.get("keyword", "").strip()
    schedule_id = request.args.get("schedule_id", "").strip()
    course_id = request.args.get("course_id", "").strip()
    teacher_id = request.args.get("teacher_id", "").strip()
    semester = request.args.get("semester", "").strip()
    day_of_week = request.args.get("day_of_week", "").strip()

    where = []
    params = []
    
    # 如果提供了schedule_id，精确匹配
    if schedule_id:
        try:
            where.append("cs.schedule_id = %s")
            params.append(int(schedule_id))
        except ValueError:
            pass
    
    # 如果提供了course_id，精确匹配
    if course_id:
        try:
            where.append("cs.course_id = %s")
            params.append(int(course_id))
        except ValueError:
            pass
    
    # 如果提供了teacher_id，精确匹配
    if teacher_id:
        try:
            where.append("cs.teacher_id = %s")
            params.append(int(teacher_id))
        except ValueError:
            pass
    
    # 如果提供了semester，精确匹配
    if semester:
        where.append("cs.semester = %s")
        params.append(semester)
    
    # 如果提供了day_of_week，精确匹配
    if day_of_week:
        where.append("cs.day_of_week = %s")
        params.append(day_of_week)
    
    # 如果只提供了keyword（通用搜索），搜索课程名、教师名
    if keyword and not (schedule_id or course_id or teacher_id or semester or day_of_week):
        where.append("(c.course_name LIKE %s OR t.name LIKE %s)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*) as total 
            FROM course_schedule cs
            LEFT JOIN courses c ON cs.course_id = c.course_id
            LEFT JOIN teachers t ON cs.teacher_id = t.teacher_id
            {where_sql}
        """, params)
        total = cur.fetchone()['total']

        cur.execute(
            f"""
            SELECT cs.*, 
                   c.course_name,
                   t.name AS teacher_name,
                   cl.building, cl.room,
                   CONCAT(cl.building, cl.room) AS classroom_name
            FROM course_schedule cs
            LEFT JOIN courses c ON cs.course_id = c.course_id
            LEFT JOIN teachers t ON cs.teacher_id = t.teacher_id
            LEFT JOIN classrooms cl ON cs.classroom_id = cl.classroom_id
            {where_sql}
            ORDER BY cs.schedule_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    schedules = [dict(r) for r in rows]
    return jsonify({
        "status": "ok",
        "data": schedules,
        "total": total,
        "page": page,
        "page_size": page_size
    })

@app.route("/api/course-schedules", methods=["POST"])
def create_course_schedule():
    """新增课程安排"""
    # 检查权限：只有管理员可以创建
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以创建课程安排"}), 403
    
    data = request.json or {}
    course_id = data.get("course_id")
    teacher_id = data.get("teacher_id")
    semester = data.get("semester", "").strip()
    day_of_week = data.get("day_of_week", "").strip()
    period_start = data.get("period_start")
    period_end = data.get("period_end")
    classroom_id = data.get("classroom_id")
    weeks = data.get("weeks", "").strip()

    # 验证必填字段
    if not course_id:
        return jsonify({"status": "error", "msg": "课程ID不能为空"}), 400
    if not teacher_id:
        return jsonify({"status": "error", "msg": "教师ID不能为空"}), 400
    if not semester:
        return jsonify({"status": "error", "msg": "学期不能为空"}), 400
    if not day_of_week:
        return jsonify({"status": "error", "msg": "星期不能为空"}), 400
    if period_start is None:
        return jsonify({"status": "error", "msg": "开始节次不能为空"}), 400
    if period_end is None:
        return jsonify({"status": "error", "msg": "结束节次不能为空"}), 400
    if not weeks:
        return jsonify({"status": "error", "msg": "周次不能为空"}), 400
    
    # 验证day_of_week
    valid_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    if day_of_week not in valid_days:
        return jsonify({"status": "error", "msg": f"星期格式错误，必须是: {', '.join(valid_days)}"}), 400
    
    # 验证节次
    try:
        course_id = int(course_id)
        teacher_id = int(teacher_id)
        period_start = int(period_start)
        period_end = int(period_end)
        if period_start < 1 or period_start > 12:
            return jsonify({"status": "error", "msg": "开始节次必须在1-12之间"}), 400
        if period_end < 1 or period_end > 12:
            return jsonify({"status": "error", "msg": "结束节次必须在1-12之间"}), 400
        if period_end < period_start:
            return jsonify({"status": "error", "msg": "结束节次不能小于开始节次"}), 400
        if classroom_id is not None:
            classroom_id = int(classroom_id) if classroom_id else None
    except (ValueError, TypeError):
        return jsonify({"status": "error", "msg": "ID或节次格式错误"}), 400

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 验证课程是否存在
            cur.execute("SELECT course_id FROM courses WHERE course_id=%s", (course_id,))
            if not cur.fetchone():
                return jsonify({"status": "error", "msg": "课程不存在"}), 400
            
            # 验证教师是否存在
            cur.execute("SELECT teacher_id FROM teachers WHERE teacher_id=%s", (teacher_id,))
            if not cur.fetchone():
                return jsonify({"status": "error", "msg": "教师不存在"}), 400
            
            # 验证教室是否存在（如果提供了）
            if classroom_id:
                cur.execute("SELECT classroom_id FROM classrooms WHERE classroom_id=%s", (classroom_id,))
                if not cur.fetchone():
                    return jsonify({"status": "error", "msg": "教室不存在"}), 400
            
            # 检查时间冲突：同一教师在同一时间不能有多个课程
            cur.execute("""
                SELECT schedule_id FROM course_schedule
                WHERE teacher_id=%s AND semester=%s AND day_of_week=%s
                AND ((period_start <= %s AND period_end >= %s) OR (period_start <= %s AND period_end >= %s))
            """, (teacher_id, semester, day_of_week, period_start, period_start, period_end, period_end))
            if cur.fetchone():
                return jsonify({"status": "error", "msg": "该教师在此时间段已有其他课程安排"}), 400
            
            # 检查教室冲突：同一教室在同一时间不能有多个课程
            if classroom_id:
                cur.execute("""
                    SELECT schedule_id FROM course_schedule
                    WHERE classroom_id=%s AND semester=%s AND day_of_week=%s
                    AND ((period_start <= %s AND period_end >= %s) OR (period_start <= %s AND period_end >= %s))
                """, (classroom_id, semester, day_of_week, period_start, period_start, period_end, period_end))
                if cur.fetchone():
                    return jsonify({"status": "error", "msg": "该教室在此时间段已被占用"}), 400
            
            # 创建课程安排记录
            cur.execute("""
            INSERT INTO course_schedule (course_id, teacher_id, semester, day_of_week, period_start, period_end, classroom_id, weeks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (course_id, teacher_id, semester, day_of_week, period_start, period_end, classroom_id, weeks))
            schedule_id = cur.lastrowid
            
            # 记录操作日志
            if user.get("user_id"):
                cur.execute("""
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "CREATE",
                    "course_schedule",
                    schedule_id,
                    f"新增课程安排: 课程ID {course_id}, 教师ID {teacher_id}, {semester}, {day_of_week} {period_start}-{period_end}节"
                ))
            
            conn.commit()
        
        return jsonify({
            "status": "ok",
            "id": schedule_id
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": f"创建失败：{str(e)}"}), 500

@app.route("/api/course-schedules/<int:sid>", methods=["PUT"])
def update_course_schedule(sid):
    """修改课程安排信息"""
    # 检查权限：只有管理员可以修改
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以修改课程安排"}), 403
    
    data = request.json or {}
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 先获取原记录
            cur.execute("SELECT * FROM course_schedule WHERE schedule_id=%s", (sid,))
            old_row = cur.fetchone()
            if not old_row:
                return jsonify({"status": "error", "msg": "课程安排不存在"}), 404
            
            old_data = dict(old_row)
            
            # 构建更新字段
            update_fields = []
            update_values = []
            changes = []
            user_id = user.get("user_id")
            
            # 可更新字段
            updatable_fields = ["course_id", "teacher_id", "semester", "day_of_week", "period_start", "period_end", "classroom_id", "weeks"]
            
            for field in updatable_fields:
                if field in data:
                    new_val = data[field]
                    old_val = old_data.get(field)
                    
                    # 处理不同类型的值
                    if field in ["course_id", "teacher_id", "period_start", "period_end"]:
                        if new_val is not None:
                            try:
                                new_val = int(new_val)
                            except (ValueError, TypeError):
                                return jsonify({"status": "error", "msg": f"{field}格式错误"}), 400
                        else:
                            continue  # 跳过None值
                    elif field == "classroom_id":
                        if new_val is not None and new_val != "":
                            try:
                                new_val = int(new_val)
                            except (ValueError, TypeError):
                                return jsonify({"status": "error", "msg": "教室ID格式错误"}), 400
                        else:
                            new_val = None
                    elif isinstance(new_val, str):
                        new_val = new_val.strip() if new_val.strip() else None
                        if field in ["semester", "day_of_week", "weeks"] and not new_val:
                            return jsonify({"status": "error", "msg": f"{field}不能为空"}), 400
                    
                    # 验证day_of_week
                    if field == "day_of_week" and new_val:
                        valid_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                        if new_val not in valid_days:
                            return jsonify({"status": "error", "msg": f"星期格式错误，必须是: {', '.join(valid_days)}"}), 400
                    
                    # 验证节次
                    if field == "period_start" and new_val:
                        if new_val < 1 or new_val > 12:
                            return jsonify({"status": "error", "msg": "开始节次必须在1-12之间"}), 400
                    if field == "period_end" and new_val:
                        if new_val < 1 or new_val > 12:
                            return jsonify({"status": "error", "msg": "结束节次必须在1-12之间"}), 400
                    
                    if old_val != new_val:
                        update_fields.append(f"{field}=%s")
                        update_values.append(new_val)
                        changes.append(f"{field}: '{old_val or ''}' -> '{new_val or ''}'")
            
            # 如果有更新，需要验证外键和时间冲突
            if update_fields:
                # 获取更新后的值用于验证
                updated_data = old_data.copy()
                field_to_value = {}
                for i, field_expr in enumerate(update_fields):
                    field_name = field_expr.split('=')[0]
                    field_to_value[field_name] = update_values[i]
                    updated_data[field_name] = update_values[i]
                
                # 验证结束节次不小于开始节次
                period_start = updated_data.get("period_start")
                period_end = updated_data.get("period_end")
                if period_start and period_end and period_end < period_start:
                    return jsonify({"status": "error", "msg": "结束节次不能小于开始节次"}), 400
                
                # 验证外键
                if "course_id" in field_to_value:
                    course_id = updated_data.get("course_id")
                    cur.execute("SELECT course_id FROM courses WHERE course_id=%s", (course_id,))
                    if not cur.fetchone():
                        return jsonify({"status": "error", "msg": "课程不存在"}), 400
                
                if "teacher_id" in field_to_value:
                    teacher_id = updated_data.get("teacher_id")
                    cur.execute("SELECT teacher_id FROM teachers WHERE teacher_id=%s", (teacher_id,))
                    if not cur.fetchone():
                        return jsonify({"status": "error", "msg": "教师不存在"}), 400
                
                if "classroom_id" in field_to_value and updated_data.get("classroom_id"):
                    classroom_id = updated_data.get("classroom_id")
                    cur.execute("SELECT classroom_id FROM classrooms WHERE classroom_id=%s", (classroom_id,))
                    if not cur.fetchone():
                        return jsonify({"status": "error", "msg": "教室不存在"}), 400
                
                # 检查时间冲突（排除当前记录）
                teacher_id = updated_data.get("teacher_id")
                semester = updated_data.get("semester")
                day_of_week = updated_data.get("day_of_week")
                period_start = updated_data.get("period_start")
                period_end = updated_data.get("period_end")
                
                cur.execute("""
                    SELECT schedule_id FROM course_schedule
                    WHERE teacher_id=%s AND semester=%s AND day_of_week=%s
                    AND schedule_id != %s
                    AND ((period_start <= %s AND period_end >= %s) OR (period_start <= %s AND period_end >= %s))
                """, (teacher_id, semester, day_of_week, sid, period_start, period_start, period_end, period_end))
                if cur.fetchone():
                    return jsonify({"status": "error", "msg": "该教师在此时间段已有其他课程安排"}), 400
                
                # 检查教室冲突
                classroom_id = updated_data.get("classroom_id")
                if classroom_id:
                    cur.execute("""
                        SELECT schedule_id FROM course_schedule
                        WHERE classroom_id=%s AND semester=%s AND day_of_week=%s
                        AND schedule_id != %s
                        AND ((period_start <= %s AND period_end >= %s) OR (period_start <= %s AND period_end >= %s))
                    """, (classroom_id, semester, day_of_week, sid, period_start, period_start, period_end, period_end))
                    if cur.fetchone():
                        return jsonify({"status": "error", "msg": "该教室在此时间段已被占用"}), 400
                
                # 执行更新
                update_values.append(sid)
                sql = f"UPDATE course_schedule SET {', '.join(update_fields)} WHERE schedule_id=%s"
                cur.execute(sql, update_values)
                
                # 记录 audit_log
                if user_id:
                    details = "; ".join(changes) if changes else "无变更"
                    cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        "UPDATE",
                        "course_schedule",
                        sid,
                        f"更新课程安排信息: {details}"
                    ))
                conn.commit()
            else:
                # 没有实际更新
                conn.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"更新失败：{str(e)}"}), 500

@app.route("/api/course-schedules/<int:sid>", methods=["DELETE"])
def delete_course_schedule(sid):
    """删除课程安排"""
    # 检查权限：只有管理员可以删除
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "只有管理员可以删除课程安排"}), 403
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 先获取课程安排信息用于日志
            cur.execute("""
                SELECT cs.*, c.course_name, t.name AS teacher_name
                FROM course_schedule cs
                LEFT JOIN courses c ON cs.course_id = c.course_id
                LEFT JOIN teachers t ON cs.teacher_id = t.teacher_id
                WHERE cs.schedule_id=%s
            """, (sid,))
            schedule = cur.fetchone()
            if not schedule:
                return jsonify({"status": "error", "msg": "课程安排不存在"}), 404
            
            schedule_data = dict(schedule)
            
            # 删除课程安排记录
            cur.execute("DELETE FROM course_schedule WHERE schedule_id=%s", (sid,))
            
            # 记录操作日志
            if user.get("user_id"):
                cur.execute("""
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "DELETE",
                    "course_schedule",
                    sid,
                    f"删除课程安排: {schedule_data.get('course_name', '')} - {schedule_data.get('teacher_name', '')} ({schedule_data.get('semester', '')}, {schedule_data.get('day_of_week', '')} {schedule_data.get('period_start', '')}-{schedule_data.get('period_end', '')}节)"
                ))
            
            conn.commit()
        
        return jsonify({"status": "ok", "msg": "删除成功"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"删除失败：{str(e)}"}), 500

@app.route("/api/scores", methods=["GET"])
def list_scores():
    """获取成绩列表，支持按学生ID、课程ID、课程名、学期搜索"""
    student_id = request.args.get("student_id")
    course_id = request.args.get("course_id")
    course_name = request.args.get("course_name")
    semester = request.args.get("semester", "").strip()
    
    where = []
    params = []
    
    if student_id:
        where.append("s.student_id=%s")
        params.append(student_id)
    
    if course_id:
        try:
            where.append("c.course_id=%s")
            params.append(int(course_id))
        except ValueError:
            pass
    
    if course_name:
        where.append("c.course_name LIKE %s")
        params.append(f"%{course_name}%")
    
    if semester:
        where.append("cs.semester = %s")
        params.append(semester)
    
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            # 使用 COALESCE 兼容没有 version 字段的情况
            cur.execute(f"""
            SELECT sc.score_id, s.student_id, s.name AS student_name,
                   c.course_id, c.course_name, cs.semester, c.credit,
                   sc.score, sc.exam_date, COALESCE(sc.version, 1) AS version
            FROM scores sc
            JOIN course_selection cs ON sc.selection_id = cs.selection_id
            JOIN students s ON cs.student_id = s.student_id
            JOIN courses c  ON cs.course_id = c.course_id
            {where_sql}
            ORDER BY sc.score_id DESC
            """, params)
            rows = cur.fetchall()
        return jsonify({"status": "ok", "data": [dict(r) for r in rows]})
    except Exception as e:
        # 如果查询失败（可能是 version 字段不存在），尝试不查询 version
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                SELECT sc.score_id, s.student_id, s.name AS student_name,
                       c.course_id, c.course_name, cs.semester, c.credit,
                       sc.score, sc.exam_date
                FROM scores sc
                JOIN course_selection cs ON sc.selection_id = cs.selection_id
                JOIN students s ON cs.student_id = s.student_id
                JOIN courses c  ON cs.course_id = c.course_id
                {where_sql}
                ORDER BY sc.score_id DESC
                """, params)
                rows = cur.fetchall()
                # 为每条记录添加默认版本号
                for row in rows:
                    if 'version' not in row:
                        row['version'] = 1
            return jsonify({"status": "ok", "data": [dict(r) for r in rows]})
        except Exception as e2:
            return jsonify({"status": "error", "msg": f"获取成绩失败：{str(e2)}"}), 500

@app.route("/api/scores", methods=["POST"])
def add_score():
    try:
        data = request.json or {}
        student_id = data.get("student_id")
        course_id = data.get("course_id")
        score = data.get("score")  # 选课时可以为空
        exam_date = data.get("exam_date")  # 选课时可以为空

        if not student_id or not course_id:
            return jsonify({"status": "error", "msg": "学生ID和课程ID不能为空"}), 400

        with get_conn() as conn:
            cur = conn.cursor()
            
            # 获取学期信息（从课程表或请求参数）
            semester = data.get("semester")
            if not semester:
                # 尝试从课程表获取默认学期
                cur.execute("SELECT semester FROM courses WHERE course_id = %s", (course_id,))
                course_info = cur.fetchone()
                if course_info and course_info.get("semester"):
                    semester = course_info["semester"]
                else:
                    semester = "2024-2025-1"  # 默认学期
            
            # 检查是否已选过该课程（同一学期）
            cur.execute("""
            SELECT selection_id FROM course_selection 
            WHERE student_id=%s AND course_id=%s AND semester=%s
            """, (student_id, course_id, semester))
            existing_selection = cur.fetchone()
            
            if existing_selection:
                # 如果已选课，检查是否已有成绩记录
                selection_id = existing_selection["selection_id"]
                cur.execute("""
                SELECT score_id FROM scores WHERE selection_id=%s
                """, (selection_id,))
                existing_score = cur.fetchone()
                
                if existing_score:
                    return jsonify({"status": "error", "msg": "已选该课程"}), 400
                else:
                    # 已有选课记录但没有成绩，创建成绩记录
                    cur.execute("""
                    INSERT INTO scores (selection_id, score, exam_date)
                    VALUES (%s, %s, %s)
                    """, (selection_id, score, exam_date))
            else:
                # 创建选课记录
                cur.execute("""
                INSERT INTO course_selection (student_id, course_id, semester)
                VALUES (%s, %s, %s)
                """, (student_id, course_id, semester))
                selection_id = cur.lastrowid
                
                # 创建成绩记录（score 和 exam_date 可以为 NULL）
                cur.execute("""
                INSERT INTO scores (selection_id, score, exam_date)
                VALUES (%s, %s, %s)
                """, (selection_id, score, exam_date))
            conn.commit()
            
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"选课失败：{str(e)}"}), 500

@app.route("/api/teacher/scores", methods=["GET"])
def get_teacher_scores():
    """获取当前教师教授的课程的学生成绩"""
    try:
        token = request.headers.get("X-Token", "")
        user = _get_user_from_token(token)
        if not user:
            return jsonify({"status": "error", "msg": "请先登录"}), 401
        if user["role"] != "teacher":
            return jsonify({"status": "error", "msg": "仅教师可以访问"}), 403

        # 获取当前教师的teacher_id
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT teacher_id FROM teachers WHERE user_id=%s
                """,
                (user["user_id"],),
            )
            teacher_row = cur.fetchone()
            if not teacher_row:
                return jsonify({"status": "error", "msg": "未找到教师档案"}), 404

            teacher_id = teacher_row["teacher_id"]

            # 获取过滤参数（转换为None或整数）
            course_id = request.args.get("course_id")
            if course_id:
                try:
                    course_id = int(course_id)
                except ValueError:
                    course_id = None
            else:
                course_id = None

            student_id = request.args.get("student_id")
            if student_id:
                try:
                    student_id = int(student_id)
                except ValueError:
                    student_id = None
            else:
                student_id = None

            course_name = request.args.get("course_name", "").strip()
            if not course_name:
                course_name = None

            # 检查 version 字段是否存在
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'scores'
                  AND COLUMN_NAME = 'version'
            """)
            has_version = cur.fetchone().get('cnt', 0) > 0

            # 构建查询（根据 version 字段是否存在选择不同的查询）
            if has_version:
                cur.execute(
                    """
                    SELECT
                        s.score_id,
                        st.student_id,
                        st.name AS student_name,
                        c.course_id,
                        c.course_name,
                        s.score,
                        cs.semester,
                        COALESCE(s.version, 1) AS version
                    FROM scores s
                    JOIN course_selection cs ON s.selection_id = cs.selection_id
                    JOIN students st ON cs.student_id = st.student_id
                    JOIN courses c   ON cs.course_id = c.course_id
                    WHERE c.teacher_id = %s
                      AND (%s IS NULL OR c.course_id = %s)
                      AND (%s IS NULL OR st.student_id = %s)
                      AND (%s IS NULL OR c.course_name LIKE %s)
                    ORDER BY st.student_id
                    """,
                    (teacher_id, course_id, course_id, student_id, student_id, 
                     course_name, f"%{course_name}%" if course_name else None),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        s.score_id,
                        st.student_id,
                        st.name AS student_name,
                        c.course_id,
                        c.course_name,
                        s.score,
                        cs.semester,
                        1 AS version
                    FROM scores s
                    JOIN course_selection cs ON s.selection_id = cs.selection_id
                    JOIN students st ON cs.student_id = st.student_id
                    JOIN courses c   ON cs.course_id = c.course_id
                    WHERE c.teacher_id = %s
                      AND (%s IS NULL OR c.course_id = %s)
                      AND (%s IS NULL OR st.student_id = %s)
                      AND (%s IS NULL OR c.course_name LIKE %s)
                    ORDER BY st.student_id
                    """,
                    (teacher_id, course_id, course_id, student_id, student_id, 
                     course_name, f"%{course_name}%" if course_name else None),
                )
            rows = cur.fetchall()

        return jsonify({"status": "ok", "data": [dict(r) for r in rows]})
    except Exception as e:
        import traceback
        print(f"get_teacher_scores 错误: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "error", "msg": f"获取成绩失败：{str(e)}"}), 500


@app.route("/api/student/schedule", methods=["GET"])
def get_student_schedule():
    """获取学生的课程表"""
    try:
        token = request.headers.get("X-Token", "")
        user = _get_user_from_token(token)
        if not user:
            return jsonify({"status": "error", "msg": "请先登录"}), 401
        
        # 获取student_id参数（可以是当前登录学生，也可以是管理员查询其他学生）
        student_id_param = request.args.get("student_id")
        semester = request.args.get("semester", "").strip()
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 如果是学生角色，只能查看自己的课程表
            if user["role"] == "student":
                # 获取当前学生的student_id
                cur.execute("SELECT student_id FROM students WHERE user_id=%s", (user["user_id"],))
                student_row = cur.fetchone()
                if not student_row:
                    return jsonify({"status": "error", "msg": "未找到学生档案"}), 404
                student_id = student_row["student_id"]
            elif user["role"] in ["admin", "teacher"]:
                # 管理员和教师可以查询指定学生的课程表
                if not student_id_param:
                    return jsonify({"status": "error", "msg": "请提供学生ID"}), 400
                try:
                    student_id = int(student_id_param)
                except ValueError:
                    return jsonify({"status": "error", "msg": "学生ID格式错误"}), 400
            else:
                return jsonify({"status": "error", "msg": "权限不足"}), 403
            
            # 查询该学生已选的课程
            where_clause = "WHERE cs.student_id = %s"
            params = [student_id]
            
            if semester:
                where_clause += " AND cs.semester = %s"
                params.append(semester)
            
            # 查询课程表信息，关联课程、教师、教室等信息
            cur.execute(f"""
                SELECT 
                    cs.course_id,
                    c.course_name,
                    c.credit,
                    cs.semester,
                    cs_schedule.schedule_id,
                    cs_schedule.day_of_week,
                    cs_schedule.period_start,
                    cs_schedule.period_end,
                    cs_schedule.weeks,
                    cl.building,
                    cl.room,
                    t.name AS teacher_name
                FROM course_selection cs
                JOIN courses c ON cs.course_id = c.course_id
                LEFT JOIN course_schedule cs_schedule ON cs.course_id = cs_schedule.course_id 
                    AND cs.semester = cs_schedule.semester
                LEFT JOIN classrooms cl ON cs_schedule.classroom_id = cl.classroom_id
                LEFT JOIN teachers t ON cs_schedule.teacher_id = t.teacher_id
                {where_clause}
                ORDER BY cs.course_id, cs_schedule.day_of_week, cs_schedule.period_start
            """, params)
            
            rows = cur.fetchall()
            
            # 组织数据：按课程分组
            schedule_data = []
            for row in rows:
                schedule_item = {
                    "course_id": row["course_id"],
                    "course_name": row["course_name"],
                    "credit": row["credit"],
                    "semester": row["semester"],
                    "schedule_id": row["schedule_id"],
                    "day_of_week": row["day_of_week"],
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "weeks": row["weeks"],
                    "classroom": f"{row['building'] or ''}{row['room'] or ''}".strip() if row.get("building") or row.get("room") else "",
                    "teacher_name": row["teacher_name"] or ""
                }
                schedule_data.append(schedule_item)
            
        return jsonify({"status": "ok", "data": schedule_data})
    except Exception as e:
        import traceback
        print(f"get_student_schedule 错误: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "error", "msg": f"获取课程表失败：{str(e)}"}), 500


@app.route("/api/teacher/schedule", methods=["GET"])
def get_teacher_schedule():
    """获取教师的课程表"""
    try:
        token = request.headers.get("X-Token", "")
        user = _get_user_from_token(token)
        if not user:
            return jsonify({"status": "error", "msg": "请先登录"}), 401
        
        # 获取teacher_id参数（可以是当前登录教师，也可以是管理员查询其他教师）
        teacher_id_param = request.args.get("teacher_id")
        semester = request.args.get("semester", "").strip()
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 如果是教师角色，只能查看自己的课程表
            if user["role"] == "teacher":
                # 获取当前教师的teacher_id
                cur.execute("SELECT teacher_id FROM teachers WHERE user_id=%s", (user["user_id"],))
                teacher_row = cur.fetchone()
                if not teacher_row:
                    return jsonify({"status": "error", "msg": "未找到教师档案"}), 404
                teacher_id = teacher_row["teacher_id"]
            elif user["role"] == "admin":
                # 管理员可以查询指定教师的课程表
                if not teacher_id_param:
                    return jsonify({"status": "error", "msg": "请提供教师ID"}), 400
                try:
                    teacher_id = int(teacher_id_param)
                except ValueError:
                    return jsonify({"status": "error", "msg": "教师ID格式错误"}), 400
            else:
                return jsonify({"status": "error", "msg": "权限不足"}), 403
            
            # 查询该教师教授的课程的课程表信息
            where_clause = "WHERE cs.teacher_id = %s"
            params = [teacher_id]
            
            if semester:
                where_clause += " AND cs.semester = %s"
                params.append(semester)
            
            # 查询课程表信息，关联课程、教室等信息
            cur.execute(f"""
                SELECT 
                    cs.course_id,
                    c.course_name,
                    c.credit,
                    cs.semester,
                    cs.schedule_id,
                    cs.day_of_week,
                    cs.period_start,
                    cs.period_end,
                    cs.weeks,
                    cl.building,
                    cl.room,
                    t.name AS teacher_name
                FROM course_schedule cs
                JOIN courses c ON cs.course_id = c.course_id
                LEFT JOIN classrooms cl ON cs.classroom_id = cl.classroom_id
                LEFT JOIN teachers t ON cs.teacher_id = t.teacher_id
                {where_clause}
                ORDER BY cs.course_id, cs.day_of_week, cs.period_start
            """, params)
            
            rows = cur.fetchall()
            
            # 组织数据：按课程分组
            schedule_data = []
            for row in rows:
                schedule_item = {
                    "course_id": row["course_id"],
                    "course_name": row["course_name"],
                    "credit": row["credit"],
                    "semester": row["semester"],
                    "schedule_id": row["schedule_id"],
                    "day_of_week": row["day_of_week"],
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "weeks": row["weeks"],
                    "classroom": f"{row['building'] or ''}{row['room'] or ''}".strip() if row.get("building") or row.get("room") else "",
                    "teacher_name": row["teacher_name"] or ""
                }
                schedule_data.append(schedule_item)
            
        return jsonify({"status": "ok", "data": schedule_data})
    except Exception as e:
        import traceback
        print(f"get_teacher_schedule 错误: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "error", "msg": f"获取课程表失败：{str(e)}"}), 500


@app.route("/api/student/my-courses", methods=["GET"])
def get_student_my_courses():
    """获取学生的已选课程列表（直接从course_selection表查询）"""
    try:
        token = request.headers.get("X-Token", "")
        user = _get_user_from_token(token)
        if not user:
            return jsonify({"status": "error", "msg": "请先登录"}), 401
        
        # 获取student_id参数（可以是当前登录学生，也可以是管理员查询其他学生）
        student_id_param = request.args.get("student_id")
        course_name = request.args.get("course_name", "").strip()
        semester = request.args.get("semester", "").strip()
        
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 如果是学生角色，只能查看自己的课程
            if user["role"] == "student":
                # 获取当前学生的student_id
                cur.execute("SELECT student_id FROM students WHERE user_id=%s", (user["user_id"],))
                student_row = cur.fetchone()
                if not student_row:
                    return jsonify({"status": "error", "msg": "未找到学生档案"}), 404
                student_id = student_row["student_id"]
            elif user["role"] in ["admin", "teacher"]:
                # 管理员和教师可以查询指定学生的课程
                if not student_id_param:
                    return jsonify({"status": "error", "msg": "请提供学生ID"}), 400
                try:
                    student_id = int(student_id_param)
                except ValueError:
                    return jsonify({"status": "error", "msg": "学生ID格式错误"}), 400
            else:
                return jsonify({"status": "error", "msg": "权限不足"}), 403
            
            # 构建查询条件
            where_clause = "WHERE cs.student_id = %s"
            params = [student_id]
            
            if course_name:
                where_clause += " AND c.course_name LIKE %s"
                params.append(f"%{course_name}%")
            
            if semester:
                where_clause += " AND cs.semester = %s"
                params.append(semester)
            
            # 查询已选课程，关联课程和教师信息
            cur.execute(f"""
                SELECT 
                    cs.course_id,
                    c.course_name,
                    c.credit,
                    cs.semester,
                    t.name AS teacher_name,
                    cs.selection_id
                FROM course_selection cs
                JOIN courses c ON cs.course_id = c.course_id
                LEFT JOIN teachers t ON c.teacher_id = t.teacher_id
                {where_clause}
                ORDER BY cs.course_id DESC
            """, params)
            
            rows = cur.fetchall()
            
            # 转换为字典列表
            courses_data = []
            for row in rows:
                course_item = {
                    "course_id": row["course_id"],
                    "course_name": row["course_name"] or "",
                    "credit": row["credit"] or 0,
                    "semester": row["semester"] or "",
                    "teacher_name": row["teacher_name"] or "",
                    "selection_id": row["selection_id"]
                }
                courses_data.append(course_item)
            
        return jsonify({"status": "ok", "data": courses_data})
    except Exception as e:
        import traceback
        print(f"get_student_my_courses 错误: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "error", "msg": f"获取已选课程失败：{str(e)}"}), 500


@app.route("/api/scores/<int:eid>", methods=["PUT"])
def update_score(eid):
    """更新成绩（教师只能更新自己课程的成绩）
    使用悲观锁（SELECT FOR UPDATE）和乐观锁（版本号）双重保护
    """
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401

    data = request.json or {}
    score = data.get("score")
    exam_date = data.get("exam_date")
    expected_version = data.get("version")  # 乐观锁：期望的版本号

    if score is None:
        return jsonify({"status": "error", "msg": "成绩不能为空"}), 400

    # 使用 REPEATABLE READ 隔离级别和悲观锁
    with get_conn(isolation_level='REPEATABLE READ') as conn:
        cur = conn.cursor()

        # 先检查 version 字段是否存在
        cur.execute("""
            SELECT COUNT(*) as cnt
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'scores'
              AND COLUMN_NAME = 'version'
        """)
        has_version = cur.fetchone().get('cnt', 0) > 0

        # 如果是教师，需要验证该课程属于该教师
        if user["role"] == "teacher":
            # 获取当前教师的teacher_id
            cur.execute(
                """
                SELECT teacher_id FROM teachers WHERE user_id=%s
                """,
                (user["user_id"],),
            )
            teacher_row = cur.fetchone()
            if not teacher_row:
                return jsonify({"status": "error", "msg": "未找到教师档案"}), 404

            teacher_id = teacher_row["teacher_id"]

            # 使用悲观锁：SELECT FOR UPDATE 锁定行，防止并发修改
            if has_version:
                cur.execute(
                    """
                    SELECT s.score_id, s.score AS old_score, COALESCE(s.version, 1) AS version, c.course_id
                    FROM scores s
                    JOIN course_selection cs ON s.selection_id = cs.selection_id
                    JOIN courses c ON cs.course_id = c.course_id
                    WHERE s.score_id = %s AND c.teacher_id = %s
                    FOR UPDATE
                    """,
                    (eid, teacher_id),
                )
            else:
                cur.execute(
                    """
                    SELECT s.score_id, s.score AS old_score, 1 AS version, c.course_id
                    FROM scores s
                    JOIN course_selection cs ON s.selection_id = cs.selection_id
                    JOIN courses c ON cs.course_id = c.course_id
                    WHERE s.score_id = %s AND c.teacher_id = %s
                    FOR UPDATE
                    """,
                    (eid, teacher_id),
                )
            score_row = cur.fetchone()
            if not score_row:
                return jsonify({"status": "error", "msg": "无权修改该成绩或成绩不存在"}), 403

            old_score = score_row["old_score"]
            current_version = score_row.get("version", 1)
        else:
            # 管理员可以修改任何成绩，使用悲观锁锁定行
            if has_version:
                cur.execute(
                    """
                    SELECT score_id, score AS old_score, COALESCE(version, 1) AS version
                    FROM scores
                    WHERE score_id = %s
                    FOR UPDATE
                    """,
                    (eid,),
                )
            else:
                cur.execute(
                    """
                    SELECT score_id, score AS old_score, 1 AS version
                    FROM scores
                    WHERE score_id = %s
                    FOR UPDATE
                    """,
                    (eid,),
                )
            score_row = cur.fetchone()
            if not score_row:
                return jsonify({"status": "error", "msg": "成绩不存在"}), 404

            old_score = score_row["old_score"]
            current_version = score_row.get("version", 1)

        # 乐观锁检查：如果提供了版本号，验证版本是否匹配
        if expected_version is not None:
            if current_version != expected_version:
                return jsonify({
                    "status": "error",
                    "msg": "数据已被其他用户修改，请刷新后重试",
                    "current_version": current_version
                }), 409  # 409 Conflict

        # 更新成绩，同时更新版本号（乐观锁）
        # 如果 version 字段不存在，只更新成绩，不更新版本号
        new_version = current_version + 1
        
        # 检查 version 字段是否存在
        cur.execute("""
            SELECT COUNT(*) as cnt
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'scores'
              AND COLUMN_NAME = 'version'
        """)
        has_version = cur.fetchone().get('cnt', 0) > 0
        
        if has_version:
            # 有 version 字段，使用乐观锁
            if exam_date:
                cur.execute(
                    """
                    UPDATE scores
                    SET score = %s, exam_date = %s, version = %s
                    WHERE score_id = %s AND version = %s
                    """,
                    (score, exam_date, new_version, eid, current_version),
                )
            else:
                cur.execute(
                    """
                    UPDATE scores
                    SET score = %s, version = %s
                    WHERE score_id = %s AND version = %s
                    """,
                    (score, new_version, eid, current_version),
                )
            
            # 检查是否成功更新（乐观锁：如果版本不匹配，rowcount 为 0）
            if cur.rowcount == 0:
                return jsonify({
                    "status": "error",
                    "msg": "更新失败：数据已被其他用户修改，请刷新后重试"
                }), 409
        else:
            # 没有 version 字段，只更新成绩（仅使用悲观锁）
            if exam_date:
                cur.execute(
                    """
                    UPDATE scores
                    SET score = %s, exam_date = %s
                    WHERE score_id = %s
                    """,
                    (score, exam_date, eid),
                )
            else:
                cur.execute(
                    """
                    UPDATE scores
                    SET score = %s
                    WHERE score_id = %s
                    """,
                    (score, eid),
                )
            new_version = current_version  # 保持原版本号

        # 记录操作日志
        if user.get("user_id"):
            cur.execute(
                """
                INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                VALUES (%s, 'update_score', 'scores', %s, %s)
                """,
                (
                    user["user_id"],
                    eid,
                    f"score changed from {old_score} to {score} (version {current_version} -> {new_version})",
                ),
            )

        conn.commit()

    return jsonify({"status": "ok", "version": new_version})

@app.route("/api/scores", methods=["DELETE"])
def delete_score():
    """删除选课记录（退课）"""
    try:
        # 支持查询参数和 JSON body 两种方式
        student_id = request.args.get("student_id") or (request.json or {}).get("student_id")
        course_id = request.args.get("course_id") or (request.json or {}).get("course_id")
        
        if not student_id or not course_id:
            return jsonify({"status": "error", "msg": "学生ID和课程ID不能为空"}), 400
        
        try:
            student_id = int(student_id)
            course_id = int(course_id)
        except ValueError:
            return jsonify({"status": "error", "msg": "学生ID和课程ID必须是数字"}), 400
        
        with get_conn() as conn:
            cur = conn.cursor()
            # 先查找选课记录
            semester = request.args.get("semester") or (request.json or {}).get("semester")
            if semester:
                cur.execute("""
                SELECT selection_id FROM course_selection 
                WHERE student_id=%s AND course_id=%s AND semester=%s
                """, (student_id, course_id, semester))
            else:
                cur.execute("""
                SELECT selection_id FROM course_selection 
                WHERE student_id=%s AND course_id=%s
                LIMIT 1
                """, (student_id, course_id))
            
            selection = cur.fetchone()
            if not selection:
                return jsonify({"status": "error", "msg": "未找到选课记录"}), 404
            
            # 删除选课记录（会自动级联删除关联的 scores 记录）
            selection_id = selection["selection_id"]
            cur.execute("""
            DELETE FROM course_selection 
            WHERE selection_id=%s
            """, (selection_id,))
            
            if cur.rowcount == 0:
                return jsonify({"status": "error", "msg": "删除失败"}), 500
            
            conn.commit()
            
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": f"退课失败：{str(e)}"}), 500

@app.route("/api/scores/batch", methods=["POST"])
def batch_import_scores():
    """批量导入成绩（仅管理员）"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以批量导入成绩"}), 403
    
    try:
        data = request.json or {}
        scores_data = data.get("scores", [])
        
        if not scores_data or not isinstance(scores_data, list):
            return jsonify({"status": "error", "msg": "请提供成绩数据列表"}), 400
        
        success_count = 0
        error_count = 0
        errors = []
        
        # 使用 SERIALIZABLE 隔离级别和表锁，确保批量操作的原子性
        with get_conn(isolation_level='SERIALIZABLE') as conn:
            cur = conn.cursor()
            
            # 检查 version 字段是否存在
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'scores'
                  AND COLUMN_NAME = 'version'
            """)
            has_version = cur.fetchone().get('cnt', 0) > 0
            
            # 获取表级锁（防止并发批量操作冲突）
            cur.execute("LOCK TABLES scores WRITE, course_selection WRITE, students READ, courses READ")
            
            try:
                for idx, score_item in enumerate(scores_data):
                    try:
                        student_id = score_item.get("student_id")
                        course_id = score_item.get("course_id")
                        score = score_item.get("score")
                        exam_date = score_item.get("exam_date")
                        semester = score_item.get("semester")
                        
                        if not student_id or not course_id:
                            error_count += 1
                            errors.append(f"第{idx+1}条：学生ID和课程ID不能为空")
                            continue
                        
                        # 如果没有提供学期，尝试从课程表获取
                        if not semester:
                            cur.execute("SELECT semester FROM courses WHERE course_id=%s", (course_id,))
                            course_info = cur.fetchone()
                            if course_info and course_info.get("semester"):
                                semester = course_info["semester"]
                            else:
                                semester = "2024-2025-1"  # 默认学期
                        
                        # 检查学生和课程是否存在
                        cur.execute("SELECT student_id FROM students WHERE student_id=%s", (student_id,))
                        if not cur.fetchone():
                            error_count += 1
                            errors.append(f"第{idx+1}条：学生ID {student_id} 不存在")
                            continue
                        
                        cur.execute("SELECT course_id FROM courses WHERE course_id=%s", (course_id,))
                        if not cur.fetchone():
                            error_count += 1
                            errors.append(f"第{idx+1}条：课程ID {course_id} 不存在")
                            continue
                        
                        # 检查是否已存在选课记录
                        cur.execute("""
                            SELECT selection_id FROM course_selection 
                            WHERE student_id=%s AND course_id=%s AND semester=%s
                            FOR UPDATE
                        """, (student_id, course_id, semester))
                        existing_selection = cur.fetchone()
                        
                        if existing_selection:
                            selection_id = existing_selection["selection_id"]
                            # 检查是否已有成绩记录
                            cur.execute("""
                                SELECT score_id FROM scores 
                                WHERE selection_id=%s
                                FOR UPDATE
                            """, (selection_id,))
                            existing_score = cur.fetchone()
                            
                            if existing_score:
                                # 更新成绩
                                cur.execute("""
                                    UPDATE scores 
                                    SET score=%s, exam_date=%s
                                    WHERE selection_id=%s
                                """, (score, exam_date, selection_id))
                                if cur.rowcount > 0:
                                    success_count += 1
                                else:
                                    error_count += 1
                                    errors.append(f"第{idx+1}条：更新失败")
                            else:
                                # 创建成绩记录
                                cur.execute("""
                                    INSERT INTO scores (selection_id, score, exam_date)
                                    VALUES (%s, %s, %s)
                                """, (selection_id, score, exam_date))
                                success_count += 1
                        else:
                            # 创建选课记录
                            cur.execute("""
                                INSERT INTO course_selection (student_id, course_id, semester)
                                VALUES (%s, %s, %s)
                            """, (student_id, course_id, semester))
                            selection_id = cur.lastrowid
                            
                            # 创建成绩记录
                            cur.execute("""
                                INSERT INTO scores (selection_id, score, exam_date)
                                VALUES (%s, %s, %s)
                            """, (selection_id, score, exam_date))
                            success_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        errors.append(f"第{idx+1}条：{str(e)}")
            finally:
                # 释放表锁
                cur.execute("UNLOCK TABLES")
            
            # 记录操作日志
            if user.get("user_id") and success_count > 0:
                cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "batch_import_scores",
                    "scores",
                    None,
                    f"批量导入成绩：成功{success_count}条，失败{error_count}条"
                ))
            
            conn.commit()
        
        return jsonify({
            "status": "ok",
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors[:20]  # 最多返回20条错误信息
        })
        
    except Exception as e:
        return jsonify({"status": "error", "msg": f"批量导入失败：{str(e)}"}), 500

@app.route("/api/scores/cleanup", methods=["POST"])
def cleanup_abnormal_scores():
    """批量清理异常成绩数据（仅管理员）"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以清理异常数据"}), 403
    
    try:
        data = request.json or {}
        cleanup_empty = data.get("cleanup_empty", False)  # 清理空成绩
        cleanup_duplicates = data.get("cleanup_duplicates", False)  # 清理重复成绩
        
        if not cleanup_empty and not cleanup_duplicates:
            return jsonify({"status": "error", "msg": "请至少选择一种清理类型"}), 400
        
        deleted_count = 0
        details = []
        
        # 使用 SERIALIZABLE 隔离级别和表锁，确保清理操作的原子性
        with get_conn(isolation_level='SERIALIZABLE') as conn:
            cur = conn.cursor()
            
            # 获取表级写锁（防止并发清理操作冲突）
            cur.execute("LOCK TABLES scores WRITE")
            
            try:
                # 清理空成绩（score为NULL的记录）
                if cleanup_empty:
                    cur.execute("""
                        SELECT score_id, selection_id 
                        FROM scores 
                        WHERE score IS NULL
                        FOR UPDATE
                    """)
                    empty_scores = cur.fetchall()
                    
                    if empty_scores:
                        cur.execute("DELETE FROM scores WHERE score IS NULL")
                        deleted_count += cur.rowcount
                        details.append(f"清理空成绩：{cur.rowcount}条")
                
                # 清理重复成绩（同一selection_id有多条记录，保留score_id最大的）
                # 注意：新架构中每个selection_id应该只有一个score，但为了兼容性保留此逻辑
                if cleanup_duplicates:
                    cur.execute("""
                        SELECT selection_id, COUNT(*) as cnt
                        FROM scores
                        GROUP BY selection_id
                        HAVING cnt > 1
                    """)
                    duplicates = cur.fetchall()
                    
                    if duplicates:
                        total_deleted = 0
                        for dup in duplicates:
                            selection_id = dup["selection_id"]
                            # 使用悲观锁获取要保留的score_id（最大的）
                            cur.execute("""
                                SELECT MAX(score_id) as max_score_id
                                FROM scores
                                WHERE selection_id=%s
                                FOR UPDATE
                            """, (selection_id,))
                            max_row = cur.fetchone()
                            if max_row and max_row["max_score_id"]:
                                max_score_id = max_row["max_score_id"]
                                # 删除除最大score_id外的所有记录
                                cur.execute("""
                                    DELETE FROM scores
                                    WHERE selection_id=%s
                                    AND score_id != %s
                                """, (selection_id, max_score_id))
                                total_deleted += cur.rowcount
                        
                        deleted_count += total_deleted
                        details.append(f"清理重复成绩：{len(duplicates)}组，共删除{total_deleted}条")
            finally:
                # 释放表锁
                cur.execute("UNLOCK TABLES")
            
            # 记录操作日志
            if user.get("user_id") and deleted_count > 0:
                cur.execute("""
                    INSERT INTO audit_log (user_id, action, target_table, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    user["user_id"],
                    "cleanup_abnormal_scores",
                    "scores",
                    None,
                    f"批量清理异常数据：共删除{deleted_count}条记录。{'；'.join(details)}"
                ))
            
            conn.commit()
        
        return jsonify({
            "status": "ok",
            "deleted_count": deleted_count,
            "details": details
        })
        
    except Exception as e:
        return jsonify({"status": "error", "msg": f"清理失败：{str(e)}"}), 500

# ---------- 统计分析 & 图表 ----------

@app.route("/api/teacher/course_stats", methods=["GET"])
def get_teacher_course_stats():
    """获取教师指定课程的统计信息"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user["role"] != "teacher":
        return jsonify({"status": "error", "msg": "仅教师可以访问"}), 403

    course_id = request.args.get("course_id")
    if not course_id:
        return jsonify({"status": "error", "msg": "请提供课程ID"}), 400

    try:
        course_id = int(course_id)
    except ValueError:
        return jsonify({"status": "error", "msg": "课程ID必须是数字"}), 400

    # 获取当前教师的teacher_id
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT teacher_id FROM teachers WHERE user_id=%s
            """,
            (user["user_id"],),
        )
        teacher_row = cur.fetchone()
        if not teacher_row:
            return jsonify({"status": "error", "msg": "未找到教师档案"}), 404

        teacher_id = teacher_row["teacher_id"]

        # (1) 基础统计
        cur.execute(
            """
            SELECT
                c.course_name,
                COUNT(s.score_id) AS total,
                AVG(s.score) AS avg_score,
                MIN(s.score) AS min_score,
                MAX(s.score) AS max_score,
                SUM(CASE WHEN s.score >= 60 THEN 1 ELSE 0 END) AS pass_count
            FROM courses c
            LEFT JOIN course_selection cs ON c.course_id = cs.course_id
            LEFT JOIN scores s ON cs.selection_id = s.selection_id
            WHERE c.course_id = %s
              AND c.teacher_id = %s
            GROUP BY c.course_name
            """,
            (course_id, teacher_id),
        )
        stats_row = cur.fetchone()

        if not stats_row:
            return jsonify({"status": "error", "msg": "课程不存在或无权访问"}), 404

        # (2) 查询所有成绩用于分段统计
        cur.execute(
            """
            SELECT s.score
            FROM scores s
            JOIN course_selection cs ON s.selection_id = cs.selection_id
            JOIN courses c ON cs.course_id = c.course_id
            WHERE c.course_id = %s
              AND c.teacher_id = %s
              AND s.score IS NOT NULL
            """,
            (course_id, teacher_id),
        )
        score_rows = cur.fetchall()
        scores = [row["score"] for row in score_rows if row["score"] is not None]

        # 分段统计
        bins = {"0-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
        for sc in scores:
            if sc < 60:
                bins["0-59"] += 1
            elif sc < 70:
                bins["60-69"] += 1
            elif sc < 80:
                bins["70-79"] += 1
            elif sc < 90:
                bins["80-89"] += 1
            else:
                bins["90-100"] += 1

        # 计算及格率
        total = stats_row["total"] or 0
        pass_count = stats_row["pass_count"] or 0
        pass_rate = pass_count / total if total > 0 else 0.0

        result = {
            "course_id": course_id,
            "course_name": stats_row["course_name"],
            "total": total,
            "avg_score": float(stats_row["avg_score"]) if stats_row["avg_score"] is not None else None,
            "min_score": float(stats_row["min_score"]) if stats_row["min_score"] is not None else None,
            "max_score": float(stats_row["max_score"]) if stats_row["max_score"] is not None else None,
            "pass_rate": round(pass_rate, 4),
            "bins": bins,
        }

    return jsonify({"status": "ok", "data": result})


@app.route("/api/stats/overview", methods=["GET"])
def stats_overview():
    return jsonify({"status": "ok", "data": get_overall_stats()})

@app.route("/api/stats/histogram", methods=["GET"])
def stats_hist():
    return jsonify({"status": "ok", "data": histogram_bins()})

@app.route("/api/charts/<string:chart_name>", methods=["GET"])
def get_chart(chart_name):
    try:
        Path(CHART_DIR).mkdir(parents=True, exist_ok=True)
        if chart_name == "score_hist.png":
            path = generate_score_histogram()
        elif chart_name == "major_pie.png":
            path = generate_major_pie()
        elif chart_name == "major_avg_bar.png":
            path = generate_major_avg_bar()
        elif chart_name == "grade_trend.png":
            path = generate_grade_trend()
        elif chart_name == "course_comparison.png":
            path = generate_course_comparison()
        elif chart_name == "score_distribution_pie.png":
            path = generate_score_distribution_pie()
        else:
            return jsonify({"status": "error", "msg": "未知图表"}), 404

        if not path or not Path(path).exists():
            return jsonify({"status": "error", "msg": "图表生成失败"}), 500

        directory = str(Path(path).parent)
        fname = Path(path).name
        return send_from_directory(directory, fname)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"生成图表失败 {chart_name}: {error_detail}")
        return jsonify({"status": "error", "msg": f"图表生成异常: {str(e)}"}), 500

# ---------- 管理员统计接口 ----------

@app.route("/api/stats/school", methods=["GET"])
def stats_school():
    """全校成绩统计"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    try:
        stats = get_school_stats()
        # 添加调试信息（可选，生产环境可以移除）
        app.logger.debug(f"全校统计结果: {stats}")
        return jsonify({"status": "ok", "data": stats})
    except Exception as e:
        app.logger.exception("获取全校统计失败：%s", e)
        return jsonify({"status": "error", "msg": f"获取统计失败：{str(e)}"}), 500

@app.route("/api/stats/debug", methods=["GET"])
def stats_debug():
    """调试接口：查看数据库中的数据情况"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 检查各表的数据量
            cur.execute("SELECT COUNT(*) as total FROM students")
            students_count = cur.fetchone()["total"]
            
            cur.execute("SELECT COUNT(*) as total FROM courses")
            courses_count = cur.fetchone()["total"]
            
            cur.execute("SELECT COUNT(*) as total FROM scores")
            scores_count = cur.fetchone()["total"]
            
            cur.execute("SELECT COUNT(*) as total FROM scores WHERE score IS NOT NULL")
            valid_scores_count = cur.fetchone()["total"]
            
            # 检查JOIN后的数据量
            cur.execute("""
                SELECT COUNT(*) as total
                FROM scores sc
                INNER JOIN course_selection cs ON sc.selection_id = cs.selection_id
                INNER JOIN students s ON cs.student_id = s.student_id
                INNER JOIN courses c ON cs.course_id = c.course_id
            """)
            join_count = cur.fetchone()["total"]
            
            return jsonify({
                "status": "ok",
                "data": {
                    "students_count": students_count,
                    "courses_count": courses_count,
                    "scores_count": scores_count,
                    "valid_scores_count": valid_scores_count,
                    "join_count": join_count
                }
            })
    except Exception as e:
        app.logger.exception("调试信息获取失败：%s", e)
        return jsonify({"status": "error", "msg": f"获取调试信息失败：{str(e)}"}), 500

@app.route("/api/stats/top_students", methods=["GET"])
def stats_top_students():
    """最高分前十学生"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    try:
        limit = int(request.args.get("limit", 10))
        app.logger.info(f"开始查询最高分前十学生，limit={limit}")
        students = get_top_students(limit)
        app.logger.info(f"查询完成，返回 {len(students)} 条记录")
        if students:
            app.logger.info(f"第一条记录示例: {students[0]}")
        return jsonify({"status": "ok", "data": students})
    except Exception as e:
        app.logger.exception("获取最高分学生失败：%s", e)
        return jsonify({"status": "error", "msg": f"获取数据失败：{str(e)}"}), 500

@app.route("/api/stats/course_comparison", methods=["GET"])
def stats_course_comparison():
    """课程平均分对比"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    return jsonify({"status": "ok", "data": get_course_avg_comparison()})

@app.route("/api/stats/major", methods=["GET"])
def stats_major():
    """按专业统计"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    return jsonify({"status": "ok", "data": get_major_stats()})

@app.route("/api/stats/grade", methods=["GET"])
def stats_grade():
    """按年级统计"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    return jsonify({"status": "ok", "data": get_grade_stats()})

@app.route("/api/stats/data_quality", methods=["GET"])
def stats_data_quality():
    """数据质量检测报告"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    issues = check_data_quality()
    return jsonify({"status": "ok", "data": issues, "count": len(issues)})

@app.route("/api/stats/comprehensive", methods=["GET"])
def stats_comprehensive():
    """综合统计 - 展示各个表的基本信息"""
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401
    if user.get("role") != "admin":
        return jsonify({"status": "error", "msg": "仅管理员可以访问"}), 403
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            stats = {}
            
            # 用户表统计
            cur.execute("SELECT COUNT(*) as total FROM users")
            stats["users"] = {
                "total": cur.fetchone()["total"],
                "by_role": {}
            }
            cur.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            for row in cur.fetchall():
                stats["users"]["by_role"][row["role"]] = row["count"]
            
            # 学生表统计
            cur.execute("SELECT COUNT(*) as total FROM students")
            stats["students"] = {
                "total": cur.fetchone()["total"],
                "by_major": {},
                "by_grade": {},
                "by_gender": {}
            }
            cur.execute("SELECT major, COUNT(*) as count FROM students WHERE major IS NOT NULL AND major != '' GROUP BY major")
            for row in cur.fetchall():
                stats["students"]["by_major"][row["major"]] = row["count"]
            cur.execute("SELECT grade, COUNT(*) as count FROM students WHERE grade IS NOT NULL GROUP BY grade ORDER BY grade")
            for row in cur.fetchall():
                stats["students"]["by_grade"][f"{row['grade']}年级"] = row["count"]
            cur.execute("SELECT gender, COUNT(*) as count FROM students GROUP BY gender")
            for row in cur.fetchall():
                stats["students"]["by_gender"][row["gender"]] = row["count"]
            
            # 教师表统计
            cur.execute("SELECT COUNT(*) as total FROM teachers")
            stats["teachers"] = {
                "total": cur.fetchone()["total"],
                "by_department": {}
            }
            cur.execute("SELECT department, COUNT(*) as count FROM teachers WHERE department IS NOT NULL AND department != '' GROUP BY department")
            for row in cur.fetchall():
                stats["teachers"]["by_department"][row["department"]] = row["count"]
            
            # 课程表统计
            cur.execute("SELECT COUNT(*) as total FROM courses")
            stats["courses"] = {
                "total": cur.fetchone()["total"],
                "by_semester": {}
            }
            cur.execute("SELECT semester, COUNT(*) as count FROM courses WHERE semester IS NOT NULL AND semester != '' GROUP BY semester")
            for row in cur.fetchall():
                stats["courses"]["by_semester"][row["semester"]] = row["count"]
            
            # 选课表统计
            cur.execute("SELECT COUNT(*) as total FROM course_selection")
            stats["course_selection"] = {
                "total": cur.fetchone()["total"],
                "by_semester": {}
            }
            cur.execute("SELECT semester, COUNT(*) as count FROM course_selection GROUP BY semester")
            for row in cur.fetchall():
                stats["course_selection"]["by_semester"][row["semester"]] = row["count"]
            
            # 成绩表统计
            cur.execute("SELECT COUNT(*) as total FROM scores")
            total_scores = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) as total FROM scores WHERE score IS NOT NULL")
            valid_scores = cur.fetchone()["total"]
            stats["scores"] = {
                "total": total_scores,
                "valid_scores": valid_scores,
                "score_distribution": {}
            }
            # 分数段分布
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN score < 60 THEN '0-59'
                        WHEN score < 70 THEN '60-69'
                        WHEN score < 80 THEN '70-79'
                        WHEN score < 90 THEN '80-89'
                        ELSE '90-100'
                    END as score_range,
                    COUNT(*) as count
                FROM scores
                WHERE score IS NOT NULL
                GROUP BY score_range
                ORDER BY score_range
            """)
            for row in cur.fetchall():
                stats["scores"]["score_distribution"][row["score_range"]] = row["count"]
            
            # 计算平均分
            cur.execute("SELECT AVG(score) as avg_score FROM scores WHERE score IS NOT NULL")
            avg_result = cur.fetchone()
            stats["scores"]["avg_score"] = round(float(avg_result["avg_score"]), 2) if avg_result["avg_score"] else None
            
            # 教室表统计
            cur.execute("SELECT COUNT(*) as total FROM classrooms")
            stats["classrooms"] = {
                "total": cur.fetchone()["total"],
                "by_building": {},
                "total_capacity": 0
            }
            cur.execute("SELECT building, COUNT(*) as count FROM classrooms WHERE building IS NOT NULL AND building != '' GROUP BY building")
            for row in cur.fetchall():
                stats["classrooms"]["by_building"][row["building"]] = row["count"]
            cur.execute("SELECT SUM(capacity) as total FROM classrooms WHERE capacity IS NOT NULL")
            capacity_result = cur.fetchone()
            stats["classrooms"]["total_capacity"] = int(capacity_result["total"]) if capacity_result["total"] else 0
            
            # 课程安排表统计
            cur.execute("SELECT COUNT(*) as total FROM course_schedule")
            stats["course_schedule"] = {
                "total": cur.fetchone()["total"],
                "by_semester": {},
                "by_day": {}
            }
            cur.execute("SELECT semester, COUNT(*) as count FROM course_schedule GROUP BY semester")
            for row in cur.fetchall():
                stats["course_schedule"]["by_semester"][row["semester"]] = row["count"]
            cur.execute("SELECT day_of_week, COUNT(*) as count FROM course_schedule GROUP BY day_of_week")
            for row in cur.fetchall():
                day_map = {"Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四", "Fri": "周五", "Sat": "周六", "Sun": "周日"}
                day_cn = day_map.get(row["day_of_week"], row["day_of_week"])
                stats["course_schedule"]["by_day"][day_cn] = row["count"]
        
        return jsonify({"status": "ok", "data": stats})
    except Exception as e:
        import traceback
        print(f"综合统计失败: {traceback.format_exc()}")
        return jsonify({"status": "error", "msg": f"获取统计失败：{str(e)}"}), 500

# ---------- 爬虫触发 ----------

@app.route("/api/crawler/run", methods=["POST"])
def run_crawler():
    """爬取示例学生数据"""
    count = crawl_dummy_students()
    return jsonify({"status": "ok", "added": count})

@app.route("/api/crawler/teachers/bupt", methods=["POST"])
def run_bupt_teachers_crawler():
    """爬取北邮计算机学院教师数据"""
    try:
        added, skipped, error = crawl_bupt_scs_teachers()
        result = {
            "status": "ok",
            "added": added,
            "skipped": skipped,
            "message": f"成功导入 {added} 名教师，跳过 {skipped} 条重复数据"
        }
        if error:
            result["warning"] = error
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "status": "error",
            "msg": f"爬取失败：{str(e)}"
        }), 500

# ---------- 大模型接口 ----------

@app.route("/api/llm_chat", methods=["POST"])
def llm_chat():
    data = request.json or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"status": "error", "msg": "问题不能为空"}), 400

    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    context = _build_user_context(user)
    prompt_for_model = (
        f"【用户背景】{context}\n【用户提问】{prompt}" if context else prompt
    )

    # 传递用户角色信息给大模型，以便使用不同的 system prompt
    user_role = user.get("role") if user else None
    reply = ask_llm(prompt_for_model, role=user_role)

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO llm_logs (user_id, role, query_text, response_summary)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    user["user_id"] if user else None,
                    user["role"] if user else None,
                    prompt,
                    reply,
                ),
            )
    except Exception as exc:
        app.logger.exception("记录 LLM 日志失败：%s", exc)

    return jsonify({"status": "ok", "reply": reply})


@app.route("/api/llm_logs", methods=["GET"])
def llm_logs():
    token = request.headers.get("X-Token", "")
    user = _get_user_from_token(token)
    if not user:
        return jsonify({"status": "error", "msg": "请先登录"}), 401

    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 100))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT query_text, response_summary, created_at
            FROM llm_logs
            WHERE user_id=%s
            ORDER BY log_id DESC
            LIMIT %s
            """,
            (user["user_id"], limit),
        )
        rows = cur.fetchall()

    for row in rows:
        created_at = row.get("created_at")
        if created_at is not None:
            row["created_at"] = created_at.isoformat(sep=" ", timespec="seconds")

    return jsonify({"status": "ok", "data": rows})

if __name__ == "__main__":
    # 生产环境你可以关 debug
    app.run(host="0.0.0.0", port=5000, debug=True)
