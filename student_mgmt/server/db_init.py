# server/db_init.py
from werkzeug.security import generate_password_hash
from .models import init_db, get_conn

def seed_data():
    with get_conn() as conn:
        cur = conn.cursor()

        # 管理员账号
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.execute("""
            INSERT INTO users (username, password_hash, role, real_name)
            VALUES (?, ?, 'admin', '系统管理员')
            """, ("admin", generate_password_hash("123456")))
            print("✅ 已创建管理员账户：用户名 admin / 密码 123456")

        # 一些示例学生
        cur.execute("SELECT COUNT(*) FROM students")
        if cur.fetchone()[0] == 0:
            students = [
                ("202401001", "张三", "男", "计算机", "计科1班", "13800000001", "zs@example.com"),
                ("202401002", "李四", "女", "人工智能", "AI1班", "13800000002", "ls@example.com"),
                ("202401003", "王五", "男", "计算机", "计科1班", "13800000003", "ww@example.com"),
            ]
            cur.executemany("""
            INSERT INTO students (student_no, name, gender, major, class_name, phone, email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, students)
            print("✅ 已插入示例学生数据")

        # 示例教师
        cur.execute("SELECT COUNT(*) FROM teachers")
        if cur.fetchone()[0] == 0:
            teachers = [
                ("T001", "钱老师", "计算机学院", "副教授", "13900000001", "qian@example.com"),
                ("T002", "孙老师", "计算机学院", "讲师", "13900000002", "sun@example.com"),
            ]
            cur.executemany("""
            INSERT INTO teachers (teacher_no, name, dept, title, phone, email)
            VALUES (?, ?, ?, ?, ?, ?)
            """, teachers)
            print("✅ 已插入示例教师数据")

        # 示例课程
        cur.execute("SELECT COUNT(*) FROM courses")
        if cur.fetchone()[0] == 0:
            courses = [
                ("C001", "高等数学", 1, 4.0, "2024-春"),
                ("C002", "Python程序设计", 2, 3.0, "2024-春"),
            ]
            cur.executemany("""
            INSERT INTO courses (course_no, name, teacher_id, credit, term)
            VALUES (?, ?, ?, ?, ?)
            """, courses)
            print("✅ 已插入示例课程数据")

        # 示例成绩
        cur.execute("SELECT COUNT(*) FROM enrollments")
        if cur.fetchone()[0] == 0:
            enrollments = [
                (1, 1, 85, "2024-春"),
                (2, 1, 92, "2024-春"),
                (1, 2, 88, "2024-春"),
                (3, 2, 75, "2024-春"),
            ]
            cur.executemany("""
            INSERT INTO enrollments (student_id, course_id, score, term)
            VALUES (?, ?, ?, ?)
            """, enrollments)
            print("✅ 已插入示例选课/成绩数据")

if __name__ == "__main__":
    init_db()
    seed_data()
    print("🎉 数据库初始化完成")
