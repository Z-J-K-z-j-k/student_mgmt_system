import random
import numpy as np
from datetime import datetime, timedelta

# =======================================================
# 1. 基础信息
# =======================================================

NUM_STUDENTS = 600     # 2023213001~2023213600
NUM_COURSES = 120      # 0012023~1202023

student_ids = [2023213000 + (i + 1) for i in range(NUM_STUDENTS)]
course_ids = [f"2023{i:03d}" for i in range(1, NUM_COURSES + 1)]

# 8 个学期（每个学期 15 门课，对应 120 门课程）
semesters = [
    ("2023-09-01", "2024-01-20"),  # 2023-2024-1
    ("2024-03-01", "2024-07-15"),  # 2023-2024-2
    ("2024-09-01", "2025-01-20"),  # 2024-2025-1
    ("2025-03-01", "2025-07-15"),  # 2024-2025-2
    ("2025-09-01", "2026-01-20"),  # 2025-2026-1
    ("2026-03-01", "2026-07-15"),  # 2025-2026-2
    ("2026-09-01", "2027-01-20"),  # 2026-2027-1
    ("2027-03-01", "2027-07-15"),  # 2026-2027-2
]

# 每学期的课程范围 15 个
semester_course_ranges = [(i * 15, (i + 1) * 15) for i in range(8)]


# =======================================================
# 2. 生成一个学期的随机日期
# =======================================================

def random_date(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")

    delta = end - start
    rand_days = random.randint(0, delta.days)
    date = start + timedelta(days=rand_days)
    return date.strftime("%Y-%m-%d")


# =======================================================
# 3. 生成单科成绩（正态分布）
# =======================================================

def random_score():
    """
    正态分布：均值 78，标准差 10
    控制在 0~100 范围内
    """
    s = np.random.normal(78, 10)

    s = min(max(s, 30), 100)  # 裁剪区间
    return round(s, 1)


# =======================================================
# 4. 给每个学生分配 40 门课程（8 学期 × 5 门）
# =======================================================

def pick_courses_for_student():
    selected = []
    for sem_index in range(8):
        start, end = semester_course_ranges[sem_index]
        # 该学期 15 门课中选 5 门
        chosen = random.sample(range(start, end), 5)
        selected.extend(chosen)
    return selected  # 返回课程索引（0~119）


# =======================================================
# 5. 生成 scores 表数据
# =======================================================

output = []

# 统计每门课被选人数，用于保证每门课 ≥ 20 人
course_count = [0] * NUM_COURSES

# 每个学生至少 40 条记录
student_courses_map = {}

for sid in student_ids:
    chosen = pick_courses_for_student()
    student_courses_map[sid] = chosen
    for c in chosen:
        course_count[c] += 1

# ------------------------------------------------------
# 修复：确保每门课至少 20 名学生
# ------------------------------------------------------

for course_index in range(NUM_COURSES):
    while course_count[course_index] < 20:
        # 随机找一个学生补上这门课
        sid = random.choice(student_ids)
        if course_index not in student_courses_map[sid]:
            student_courses_map[sid].append(course_index)
            course_count[course_index] += 1


# =======================================================
# 6. 组合最终 SQL
# =======================================================

for sid in student_ids:
    course_indices = student_courses_map[sid]
    for ci in course_indices:
        course_id = course_ids[ci]

        # 找到课程对应的学期
        sem_index = ci // 15
        start, end = semesters[sem_index]

        exam_date = random_date(start, end)
        score = random_score()

        sql = f"({sid}, {course_id}, {score}, '{exam_date}')"
        output.append(sql)

# =======================================================
# 7. 写入 scores.sql
# =======================================================

with open("scores.sql", "w", encoding="utf-8") as f:
    f.write("INSERT INTO scores (student_id, course_id, score, exam_date) VALUES\n")
    f.write(",\n".join(output))
    f.write(";")

print(f"🎉 已生成 scores.sql")
print(f"📌 共生成 {len(output)} 条成绩记录（预计约 24000 条）")
print(f"📌 每个学生 40+ 门课程，每门课程 20+ 条记录")
