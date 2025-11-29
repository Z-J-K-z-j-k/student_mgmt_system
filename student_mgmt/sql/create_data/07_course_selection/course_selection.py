import random

# ---------------------------
# 1. 课程名称（必须与 courses.sql 一致）
# ---------------------------

general_courses = [
    "大学英语A","大学英语B","高等数学A1","高等数学A2","线性代数","概率论与数理统计",
    "思想道德与法治","马克思主义基本原理","中国近现代史纲要","形势与政策",
    "大学体育1","大学体育2","军事理论","创新创业基础","心理健康教育",
    "大学物理A","大学物理B","大学写作","哲学与人生","逻辑学基础",
    "美术鉴赏","音乐鉴赏","公共演讲","法律基础","工程伦理",
    "职业规划","跨文化沟通","美学概论","计算思维基础","专业导论"
]

basic_courses = [
    "C语言程序设计","面向对象程序设计","数据结构","离散数学","数字逻辑","电路与电子技术",
    "数据库系统原理","算法设计与分析","计算机组成原理","操作系统基础",
    "计算机网络基础","Java程序设计","Python程序设计","编译原理","软件工程基础",
    "人工智能导论","电子电路实验","大数据技术基础","嵌入式系统基础","信号与系统",
    "线性系统理论","移动应用基础","信息系统分析","互联网技术基础","物联网概论",
    "网络与通信基础","工程数学","数字图像处理基础","程序设计实验","电路分析基础"
]

core_courses = [
    "机器学习","深度学习","自然语言处理","计算机视觉","嵌入式系统设计","操作系统原理",
    "高级数据结构","模式识别","网络安全技术","智能机器人基础",
    "云计算技术","大数据存储系统","强化学习","推荐系统","智能控制",
    "软件体系结构","分布式系统","移动互联网技术","虚拟现实原理","人机交互技术",
    "人工神经网络","高性能计算","密码学","区块链原理","数据库高级专题",
    "机器学习工程实践","算法高级专题","跨媒体计算","多模态学习","智能感知技术"
]

elective_courses = [
    "数字媒体技术","现代密码学","智能机器人","Java Web开发","Python应用开发",
    "Web前端开发","大数据可视化","游戏设计基础","虚拟现实技术","数据挖掘",
    "信息检索","计算摄影学","人工智能伦理","现代通信系统","区块链应用开发",
    "动画技术基础","Web3技术基础","移动端UI设计","智能家居技术","智能驾驶入门",
    "图形学基础","音频信号处理","视频编码技术","数字孪生技术","机器人操作系统ROS",
    "数据隐私保护","程序语言理论","知识图谱技术","自然科学导论","脑机接口基础"
]

all_courses = general_courses + basic_courses + core_courses + elective_courses
assert len(all_courses) == 120, f"课程数量不是 120，而是 {len(all_courses)}"

# ---------------------------
# 2. 学期配置（和 courses.sql 一致）
# ---------------------------

semesters = [
    "2023-2024-1", "2023-2024-2",
    "2024-2025-1", "2024-2025-2",
    "2025-2026-1", "2025-2026-2",
    "2026-2027-1", "2026-2027-2"
]

# teacher_id：1~60，每人 2 门课
teacher_ids = [i for i in range(1, 61)]
teacher_pool = [tid for tid in teacher_ids for _ in range(2)]
random.shuffle(teacher_pool)

# ---------------------------
# 3. 构建 courses_meta（课程 → semester / teacher）
# ---------------------------

courses_meta = []  # 每个元素：{"course_id": int, "teacher_id": int, "semester": str}

course_counter = 1
idx = 0

for sem in semesters:
    for _ in range(15):
        teacher_id = int(teacher_pool[idx])
        course_id = int(f"2023{course_counter:03d}")  # 2023001~2023120

        courses_meta.append({
            "course_id": course_id,
            "teacher_id": teacher_id,
            "semester": sem,
        })

        idx += 1
        course_counter += 1

# ---------------------------
# 4. 排课规则（支持冲突检测）
# ---------------------------

days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
slots = [
    (1, 2), (3, 4), (5, 6),
    (7, 8), (9, 10), (11, 12), (13, 14)
]

# 使用你数据库中 classroom_id = 1~200
classrooms = list(range(1, 201))

def weeks_pattern():
    r = random.random()
    if r < 0.7:
        return "1-16"
    elif r < 0.85:
        return "1-8"
    else:
        return "9-16"

def sessions_per_week():
    r = random.random()
    if r < 0.7:
        return 1
    elif r < 0.95:
        return 2
    else:
        return 3

slot_teacher = {}   # (sem, day, s, e) → teacher_id set
slot_classroom = {} # (sem, day, s, e) → classroom_id set

def can_place(semester, day, slot, teacher_id, classroom_id):
    key = (semester, day, slot[0], slot[1])
    tset = slot_teacher.get(key, set())
    cset = slot_classroom.get(key, set())
    return (teacher_id not in tset) and (classroom_id not in cset)

def place(semester, day, slot, teacher_id, classroom_id):
    key = (semester, day, slot[0], slot[1])
    slot_teacher.setdefault(key, set()).add(teacher_id)
    slot_classroom.setdefault(key, set()).add(classroom_id)

# ---------------------------
# 5. 生成排课数据
# ---------------------------

records = []

for course in courses_meta:
    cid = course["course_id"]
    tid = course["teacher_id"]
    sem = course["semester"]

    # 每周 1～3 次课
    times_per_week = sessions_per_week()

    # 从 5 天里选 times_per_week 个不同天
    chosen_days = random.sample(days, min(times_per_week, len(days)))

    for day in chosen_days:
        ok = False
        for _ in range(200):
            slot = random.choice(slots)
            classroom_id = random.choice(classrooms)

            if can_place(sem, day, slot, tid, classroom_id):
                place(sem, day, slot, tid, classroom_id)
                records.append((cid, tid, sem, day, slot[0], slot[1], classroom_id, weeks_pattern()))
                ok = True
                break

        if not ok:
            print(f"⚠ 课程 {cid} 找不到合适时间段，跳过一节课。")

print(f"📚 总排课记录：{len(records)} 条")

# ---------------------------
# 6. 写入 SQL 文件
# ---------------------------

lines = []
for r in records:
    course_id, teacher_id, semester, day, ps, pe, classroom_id, weeks = r
    line = f"({course_id}, {teacher_id}, '{semester}', '{day}', {ps}, {pe}, {classroom_id}, '{weeks}')"
    lines.append(line)

sql = "INSERT INTO course_schedule (course_id, teacher_id, semester, day_of_week, period_start, period_end, classroom_id, weeks) VALUES\n"
sql += ",\n".join(lines) + ";\n"

with open("course_schedule.sql", "w", encoding="utf-8") as f:
    f.write(sql)

print("✅ 已生成 course_schedule.sql")
