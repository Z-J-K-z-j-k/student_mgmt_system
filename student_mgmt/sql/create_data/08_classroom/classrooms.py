import random

buildings = ["教二", "教三", "教四", "主楼"]

# 每栋 5 层，每层 10 个教室 → 共 50 间
FLOORS = range(1, 6)      # 1~5 层
ROOMS = range(1, 11)      # 每层 10 间

output = []
classroom_id = 1

for building in buildings:
    for floor in FLOORS:
        for num in ROOMS:
            room_name = f"{floor:01d}{num:02d}"   # 如 101、203、510
            capacity = random.randint(60, 120)

            sql = f"({classroom_id}, '{building}', '{room_name}', {capacity})"
            output.append(sql)
            classroom_id += 1


# 写入 SQL 文件
with open("classrooms.sql", "w", encoding="utf-8") as f:
    f.write("INSERT INTO classrooms (classroom_id, building, room, capacity) VALUES\n")
    f.write(",\n".join(output))
    f.write(";\n")

print(f"🎉 已生成 classrooms.sql，共 {len(output)} 条教室记录！")
