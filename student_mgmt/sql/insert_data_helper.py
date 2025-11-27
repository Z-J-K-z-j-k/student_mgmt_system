"""
辅助脚本：用于生成密码哈希并插入数据到数据库
使用方法：python student_mgmt/sql/insert_data_helper.py
"""
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from werkzeug.security import generate_password_hash
from server.models import get_conn
from datetime import date

def insert_sample_data():
    """插入示例数据"""
    with get_conn() as conn:
        cur = conn.cursor()
        
        # 1. 插入用户
        users_data = [
            ("student02", "123456", "student"),
            ("student03", "123456", "student"),
            ("teacher02", "123456", "teacher"),
            ("teacher03", "123456", "teacher"),
        ]
        
        user_ids = {}
        for username, password, role in users_data:
            # 检查是否已存在
            cur.execute("SELECT user_id FROM users WHERE username=%s", (username,))
            existing = cur.fetchone()
            if existing:
                user_ids[username] = existing['user_id']
                print(f"⚠ 用户 {username} 已存在，跳过")
                continue
            
            password_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, password_hash, role)
            )
            user_id = cur.lastrowid
            user_ids[username] = user_id
            print(f"✅ 插入用户：{username} (user_id={user_id})")
        
        # 2. 插入学生
        students_data = [
            (user_ids.get("student02"), "赵六", "male", 20, "软件工程", 2, "软工1班", "13800000004", "zl@example.com", 3.6),
            (user_ids.get("student03"), "孙七", "female", 19, "数据科学", 1, "数据1班", "13800000005", "sq@example.com", 3.9),
        ]
        
        student_ids = []
        for user_id, name, gender, age, major, grade, class_name, phone, email, gpa in students_data:
            if not user_id:
                print(f"⚠ 跳过学生 {name}：找不到对应的 user_id")
                continue
            
            cur.execute("""
                INSERT INTO students (user_id, name, gender, age, major, grade, class_name, phone, email, gpa)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, name, gender, age, major, grade, class_name, phone, email, gpa))
            student_ids.append(cur.lastrowid)
            print(f"✅ 插入学生：{name} (student_id={cur.lastrowid})")
        
        # 3. 插入教师
        teachers_data = [
            (user_ids.get("teacher02"), "周老师", "计算机学院", "教授", "13900000003", "zhou@example.com", "深度学习"),
            (user_ids.get("teacher03"), "吴老师", "计算机学院", "副教授", "13900000004", "wu@example.com", "计算机视觉"),
        ]
        
        teacher_ids = []
        for user_id, name, department, title, phone, email, research in teachers_data:
            if not user_id:
                print(f"⚠ 跳过教师 {name}：找不到对应的 user_id")
                continue
            
            cur.execute("""
                INSERT INTO teachers (user_id, name, department, title, phone, email, research)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, name, department, title, phone, email, research))
            teacher_ids.append(cur.lastrowid)
            print(f"✅ 插入教师：{name} (teacher_id={cur.lastrowid})")
        
        # 4. 插入课程（需要先有教师）
        # 获取第一个教师ID
        cur.execute("SELECT teacher_id FROM teachers LIMIT 1")
        first_teacher = cur.fetchone()
        teacher_id = first_teacher['teacher_id'] if first_teacher else None
        
        if teacher_id:
            courses_data = [
                ("数据结构", teacher_id, 4, "2024-秋"),
                ("操作系统", teacher_id, 3, "2024-秋"),
                ("计算机网络", teacher_id, 3, "2024-秋"),
            ]
            
            course_ids = []
            for course_name, t_id, credit, semester in courses_data:
                cur.execute("""
                    INSERT INTO courses (course_name, teacher_id, credit, semester)
                    VALUES (%s, %s, %s, %s)
                """, (course_name, t_id, credit, semester))
                course_ids.append(cur.lastrowid)
                print(f"✅ 插入课程：{course_name} (course_id={cur.lastrowid})")
            
            # 5. 插入成绩（需要先有学生和课程）
            if student_ids and course_ids:
                scores_data = [
                    (student_ids[0], course_ids[0], 88.5, date(2024, 12, 15)),
                    (student_ids[0], course_ids[1], 92.0, date(2024, 12, 20)),
                    (student_ids[1] if len(student_ids) > 1 else student_ids[0], course_ids[0], 95.0, date(2024, 12, 15)),
                    (student_ids[1] if len(student_ids) > 1 else student_ids[0], course_ids[2] if len(course_ids) > 2 else course_ids[0], 89.5, date(2024, 12, 25)),
                ]
                
                for student_id, course_id, score, exam_date in scores_data:
                    try:
                        cur.execute("""
                            INSERT INTO scores (student_id, course_id, score, exam_date)
                            VALUES (%s, %s, %s, %s)
                        """, (student_id, course_id, score, exam_date))
                        print(f"✅ 插入成绩：student_id={student_id}, course_id={course_id}, score={score}")
                    except Exception as e:
                        print(f"⚠ 插入成绩失败（可能已存在）：{e}")
        
        print("\n🎉 数据插入完成！")
        print("\n现在可以运行程序查看这些数据：")
        print("1. 启动服务器：python student_mgmt/server/app.py")
        print("2. 启动客户端：python student_mgmt/client/main.py")
        print("3. 使用以下账号登录：")
        print("   - student02 / 123456 (学生)")
        print("   - student03 / 123456 (学生)")
        print("   - teacher02 / 123456 (教师)")
        print("   - teacher03 / 123456 (教师)")

if __name__ == "__main__":
    try:
        insert_sample_data()
    except Exception as e:
        print(f"❌ 插入数据时出错：{e}")
        import traceback
        traceback.print_exc()

