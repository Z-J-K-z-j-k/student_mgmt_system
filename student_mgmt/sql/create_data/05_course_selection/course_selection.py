import random

# ============================
# 1. 学生 & 课程编号区间
# ============================

students = list(range(2023213001, 2023213601))   # 600 students
courses = [f"2023{i:03d}" for i in range(1, 121)]  # 120 courses: 0012023~1202023

# ============================
# 2. 学期（对应 120 门课）
# ============================

semesters = [
    "2023-2024-1", "2023-2024-2",
    "2024-2025-1", "2024-2025-2",
    "2025-2026-1", "2025-2026-2",
    "2026-2027-1", "2026-2027-2"
]

# 15 门课对应一个学期
course_by_semester = {}
idx = 0
for sem in semesters:
    course_by_semester[sem] = courses[idx:idx+15]
    idx += 15

# ============================
# 3. 为每名学生每学期随机选 5 门课
# ============================

output = []
selection_counter = 1

for student_id in students:
    for sem in semesters:
        available_courses = course_by_semester[sem]

        # 每个学期从 15 门课里随机选 5 门
        selected = random.sample(available_courses, 5)

        for cid in selected:
            sql = f"({selection_counter}, {student_id}, '{cid}', '{sem}')"
            output.append(sql)
            selection_counter += 1

# ============================
# 4. 写入文件
# ============================

with open("course_selection.sql", "w", encoding="utf-8") as f:
    f.write("INSERT INTO course_selection (selection_id, student_id, course_id, semester) VALUES\n")
    f.write(",\n".join(output))
    f.write(";\n")

print("🎉 已生成 course_selection.sql 文件，共", len(output), "条记录")
