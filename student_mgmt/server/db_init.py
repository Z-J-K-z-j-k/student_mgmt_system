# server/db_init.py
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

# 兼容直接运行脚本（python student_mgmt/server/db_init.py）
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from server.models import init_db, get_conn
else:
    from .models import init_db, get_conn

def seed_data():
    """
    初始化示例数据
    注意：字段名需要与 create_table.sql 中的表结构一致
    """
    with get_conn() as conn:
        cur = conn.cursor()

        # 默认账号（管理员 + 示范教师/学生）
        # 注意：create_table.sql 中 users 表字段为 user_id, username, password, role
        default_accounts = [
            ("admin", "123456", "admin"),
            ("teacher01", "123456", "teacher"),
            ("student01", "123456", "student"),
        ]
        for username, password, role in default_accounts:
            cur.execute("SELECT user_id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                continue
            cur.execute("""
            INSERT INTO users (username, password, role)
            VALUES (%s, %s, %s)
            """, (username, generate_password_hash(password), role))
            print(f"✅ 已创建{role}账户：{username} / {password}")

        # 一些示例学生
        # 注意：需要先获取 user_id，然后插入 students 表
        cur.execute("SELECT COUNT(*) as count FROM students")
        result = cur.fetchone()
        if result and result['count'] == 0:
            # 获取学生用户的 user_id
            cur.execute("SELECT user_id FROM users WHERE username='student01'")
            student_user_id = cur.fetchone()
            student_user_id = student_user_id['user_id'] if student_user_id else None
            
            students = [
                (student_user_id, "张三", "male", 20, "计算机", 1, "计科1班", "13800000001", "zs@example.com", 3.5),
                (student_user_id, "李四", "female", 19, "人工智能", 1, "AI1班", "13800000002", "ls@example.com", 3.8),
                (student_user_id, "王五", "male", 20, "计算机", 1, "计科1班", "13800000003", "ww@example.com", 3.2),
            ]
            cur.executemany("""
            INSERT INTO students (user_id, name, gender, age, major, grade, class_name, phone, email, gpa)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, students)
            print("✅ 已插入示例学生数据")

        # 示例教师
        cur.execute("SELECT COUNT(*) as count FROM teachers")
        result = cur.fetchone()
        if result and result['count'] == 0:
            # 获取教师用户的 user_id
            cur.execute("SELECT user_id FROM users WHERE username='teacher01'")
            teacher_user_id = cur.fetchone()
            teacher_user_id = teacher_user_id['user_id'] if teacher_user_id else None
            
            teachers = [
                (teacher_user_id, "钱老师", "计算机学院", "副教授", "13900000001", "qian@example.com", "机器学习"),
                (teacher_user_id, "孙老师", "计算机学院", "讲师", "13900000002", "sun@example.com", "数据库系统"),
            ]
            cur.executemany("""
            INSERT INTO teachers (user_id, name, department, title, phone, email, research)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, teachers)
            print("✅ 已插入示例教师数据")

        # 示例课程
        cur.execute("SELECT COUNT(*) as count FROM courses")
        result = cur.fetchone()
        if result and result['count'] == 0:
            # 获取教师ID
            cur.execute("SELECT teacher_id FROM teachers LIMIT 1")
            teacher_row = cur.fetchone()
            teacher_id = teacher_row['teacher_id'] if teacher_row else None
            
            courses = [
                (1001, "高等数学", teacher_id, 4, "2024-春"),
                (1002, "Python程序设计", teacher_id, 3, "2024-春"),
            ]
            cur.executemany("""
            INSERT INTO courses (course_id, course_name, teacher_id, credit, semester)
            VALUES (%s, %s, %s, %s, %s)
            """, courses)
            print("✅ 已插入示例课程数据")

        # 示例成绩
        cur.execute("SELECT COUNT(*) as count FROM scores")
        result = cur.fetchone()
        if result and result['count'] == 0:
            # 获取学生和课程ID
            cur.execute("SELECT student_id FROM students LIMIT 3")
            student_ids = [row['student_id'] for row in cur.fetchall()]
            cur.execute("SELECT course_id FROM courses LIMIT 2")
            course_ids = [row['course_id'] for row in cur.fetchall()]
            
            if student_ids and course_ids:
                from datetime import date
                semester = "2024-春"
                # 先创建选课记录，然后创建成绩记录
                for student_id, course_id, score, exam_date in [
                    (student_ids[0], course_ids[0], 85.0, date(2024, 6, 15)),
                    (student_ids[1], course_ids[0], 92.0, date(2024, 6, 15)),
                    (student_ids[0], course_ids[1], 88.0, date(2024, 6, 20)),
                    (student_ids[2] if len(student_ids) > 2 else student_ids[0], course_ids[1], 75.0, date(2024, 6, 20)),
                ]:
                    # 检查是否已有选课记录
                    cur.execute("""
                        SELECT selection_id FROM course_selection 
                        WHERE student_id=%s AND course_id=%s AND semester=%s
                    """, (student_id, course_id, semester))
                    selection = cur.fetchone()
                    
                    if selection:
                        selection_id = selection['selection_id']
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
                print("✅ 已插入示例成绩数据")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库初始化脚本')
    parser.add_argument('--seed', action='store_true', help='是否插入示例数据（默认不插入）')
    args = parser.parse_args()
    
    print("=" * 60)
    print("数据库初始化")
    print("=" * 60)
    print("⚠ 注意：此脚本只会创建不存在的表，不会删除现有表和数据")
    print()
    
    init_db()
    
    if args.seed:
        print()
        print("=" * 60)
        print("插入示例数据")
        print("=" * 60)
        seed_data()
    else:
        print()
        print("ℹ 跳过示例数据插入（如需插入，请使用 --seed 参数）")
    
    print()
    print("🎉 数据库初始化完成")
