# server/analysis.py
import pandas as pd
from .models import get_conn

def load_scores_df():
    """加载成绩数据，使用INNER JOIN确保数据完整性"""
    try:
        with get_conn() as conn:
            df = pd.read_sql_query("""
            SELECT sc.score_id, s.student_id, s.name AS student_name,
                   c.course_id, c.course_name,
                   sc.score, sc.exam_date, s.major, s.class_name,
                   cs.semester
            FROM scores sc
            INNER JOIN course_selection cs ON sc.selection_id = cs.selection_id
            INNER JOIN students s ON cs.student_id = s.student_id
            INNER JOIN courses c  ON cs.course_id = c.course_id
            """, conn)
        return df
    except Exception as e:
        # 如果查询失败，返回空DataFrame
        import traceback
        print(f"load_scores_df 错误: {e}")
        print(traceback.format_exc())
        return pd.DataFrame()

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

def get_school_stats():
    """全校成绩统计"""
    try:
        # 先获取学生总数（直接从students表）
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total FROM students")
            total_students_result = cur.fetchone()
            total_students = int(total_students_result["total"]) if total_students_result else 0
            
            # 检查scores表中是否有数据
            cur.execute("SELECT COUNT(*) as total FROM scores")
            scores_count_result = cur.fetchone()
            scores_count = int(scores_count_result["total"]) if scores_count_result else 0
            
            # 检查scores表中有成绩的记录数（score不为NULL）
            cur.execute("SELECT COUNT(*) as total FROM scores WHERE score IS NOT NULL")
            valid_scores_result = cur.fetchone()
            valid_scores_count = int(valid_scores_result["total"]) if valid_scores_result else 0
        
        # 如果没有成绩记录，直接返回
        if scores_count == 0:
            return {
                "avg_score": None,
                "pass_rate": None,
                "excellent_rate": None,
                "total_students": total_students,
                "total_records": 0
            }
        
        # 如果有成绩记录，使用pandas进行统计
        df = load_scores_df()
        if df.empty:
            # 如果JOIN后为空，说明scores表有数据但关联不上students或courses
            # 这种情况下，至少返回总学生数和总记录数（scores表的总记录数）
            return {
                "avg_score": None,
                "pass_rate": None,
                "excellent_rate": None,
                "total_students": total_students,
                "total_records": scores_count  # 返回scores表的总记录数
            }
        
        # 统计总学生数（所有选课记录中的唯一学生数）
        total_students_in_scores = int(df["student_id"].nunique()) if not df.empty else 0
        total_records_all = len(df)  # JOIN后的记录数
        
        # 过滤掉空成绩（只统计有成绩的记录，用于计算平均分等统计值）
        df_valid = df[df["score"].notna()]
        
        # 计算统计值（只基于有成绩的记录）
        if df_valid.empty:
            # 如果所有记录的score都是NULL，返回总记录数但统计值为None
            return {
                "avg_score": None,
                "pass_rate": None,
                "excellent_rate": None,
                "total_students": max(total_students, total_students_in_scores),
                "total_records": total_records_all  # 返回所有记录数，包括score为NULL的
            }
        
        # 计算统计值
        avg_score = df_valid["score"].mean()
        pass_rate = (df_valid["score"] >= 60).mean()
        excellent_rate = (df_valid["score"] >= 90).mean()
        
        # 确保所有值都是 Python 原生类型，处理 NaN 情况
        # total_records 返回所有记录数（包括score为NULL的），这样更准确
        return {
            "avg_score": round(float(avg_score), 2) if pd.notna(avg_score) else None,
            "pass_rate": round(float(pass_rate), 4) if pd.notna(pass_rate) else None,
            "excellent_rate": round(float(excellent_rate), 4) if pd.notna(excellent_rate) else None,
            "total_students": max(total_students, total_students_in_scores),
            "total_records": int(total_records_all) if pd.notna(total_records_all) else scores_count  # 返回所有记录数
        }
    except Exception as e:
        # 如果出错，返回空数据
        import traceback
        print(f"get_school_stats 错误: {e}")
        print(traceback.format_exc())
        # 即使出错，也尝试获取学生总数和成绩记录数
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) as total FROM students")
                total_students_result = cur.fetchone()
                total_students = int(total_students_result["total"]) if total_students_result else 0
                
                # 尝试获取scores表的记录数
                cur.execute("SELECT COUNT(*) as total FROM scores")
                scores_count_result = cur.fetchone()
                scores_count = int(scores_count_result["total"]) if scores_count_result else 0
        except:
            total_students = 0
            scores_count = 0
        
        return {
            "avg_score": None,
            "pass_rate": None,
            "excellent_rate": None,
            "total_students": total_students,
            "total_records": scores_count  # 即使出错也返回scores表的记录数
        }

def get_top_students(limit=10):
    """
    获取最高分前十学生（按加权平均分排序）
    
    加权平均分公式：加权平均分 = Σ(成绩 × 学分) / Σ(学分)
    """
    try:
        with get_conn() as conn:
            # 先检查是否有成绩数据
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total FROM scores WHERE score IS NOT NULL")
            scores_count = cur.fetchone()["total"]
            print(f"[DEBUG] 数据库中有 {scores_count} 条有效成绩记录")
            
            if scores_count == 0:
                print("[DEBUG] 数据库中没有成绩数据，返回空列表")
                return []
            
            # 检查学生和课程关联情况
            cur.execute("""
                SELECT COUNT(*) as total
                FROM scores sc
                INNER JOIN course_selection cs ON sc.selection_id = cs.selection_id
                INNER JOIN students s ON cs.student_id = s.student_id
                LEFT JOIN courses c ON cs.course_id = c.course_id
                WHERE sc.score IS NOT NULL
            """)
            join_count = cur.fetchone()["total"]
            print(f"[DEBUG] JOIN后的有效记录数: {join_count}")
            
            if join_count == 0:
                print("[DEBUG] JOIN后没有有效记录，返回空列表")
                return []
            
            # 使用加权平均分公式：Σ(成绩 × 学分) / Σ(学分)
            # 如果学分不存在或为0，使用默认学分1
            query_sql = """
            SELECT 
                s.student_id, 
                s.name AS student_name, 
                s.major, 
                s.grade,
                -- 加权平均分 = Σ(成绩 × 学分) / Σ(学分)
                SUM(sc.score * COALESCE(NULLIF(c.credit, 0), 1)) / SUM(COALESCE(NULLIF(c.credit, 0), 1)) AS weighted_avg_score,
                COUNT(sc.score_id) AS course_count,
                SUM(COALESCE(NULLIF(c.credit, 0), 1)) AS total_credits
            FROM students s
            INNER JOIN course_selection cs ON s.student_id = cs.student_id
            INNER JOIN scores sc ON cs.selection_id = sc.selection_id
            LEFT JOIN courses c ON cs.course_id = c.course_id
            WHERE sc.score IS NOT NULL
            GROUP BY s.student_id, s.name, s.major, s.grade
            HAVING COUNT(sc.score_id) > 0
            ORDER BY weighted_avg_score DESC
            LIMIT %s
            """
            print(f"[DEBUG] 执行查询，limit={limit}")
            df = pd.read_sql_query(query_sql, conn, params=(limit,))
            print(f"[DEBUG] 查询返回 {len(df)} 行数据")
            
            if not df.empty:
                print(f"[DEBUG] 前3条数据预览:")
                for idx, row in df.head(3).iterrows():
                    print(f"  学生ID: {row['student_id']}, 姓名: {row['student_name']}, 加权平均分: {row['weighted_avg_score']:.2f}")
        
        if df.empty:
            print("[DEBUG] DataFrame为空，返回空列表")
            return []
        
        # 转换为 Python 原生类型
        records = []
        for _, row in df.iterrows():
            try:
                weighted_avg = float(row["weighted_avg_score"]) if pd.notna(row["weighted_avg_score"]) else 0.0
                record = {
                    "student_id": int(row["student_id"]) if pd.notna(row["student_id"]) else None,
                    "student_name": str(row["student_name"]) if pd.notna(row["student_name"]) else "",
                    "major": str(row["major"]) if pd.notna(row["major"]) else "",
                    "grade": int(row["grade"]) if pd.notna(row["grade"]) else None,
                    "avg_score": round(weighted_avg, 2),  # 保留2位小数
                    "course_count": int(row["course_count"]) if pd.notna(row["course_count"]) else 0
                }
                records.append(record)
            except Exception as e:
                print(f"[WARNING] 转换记录时出错: {e}, 跳过该记录")
                continue
        
        print(f"[DEBUG] 成功转换 {len(records)} 条记录")
        if records:
            print(f"[DEBUG] 第一条记录: {records[0]}")
        
        return records
    except Exception as e:
        import traceback
        error_msg = f"get_top_students 错误: {e}"
        print(f"[ERROR] {error_msg}")
        print(traceback.format_exc())
        return []

def get_course_avg_comparison():
    """课程平均分对比"""
    with get_conn() as conn:
        df = pd.read_sql_query("""
        SELECT c.course_id, c.course_name,
               AVG(sc.score) AS avg_score,
               COUNT(sc.score_id) AS student_count,
               SUM(CASE WHEN sc.score >= 60 THEN 1 ELSE 0 END) AS pass_count
        FROM courses c
        LEFT JOIN course_selection cs ON c.course_id = cs.course_id
        LEFT JOIN scores sc ON cs.selection_id = sc.selection_id
        WHERE sc.score IS NOT NULL
        GROUP BY c.course_id, c.course_name
        HAVING COUNT(sc.score_id) > 0
        ORDER BY avg_score DESC
        """, conn)
    
    if df.empty:
        return []
    
    # 转换为字典列表，处理NaN值
    result = []
    for _, row in df.iterrows():
        result.append({
            "course_id": int(row["course_id"]),
            "course_name": row["course_name"],
            "avg_score": round(float(row["avg_score"]), 2) if pd.notna(row["avg_score"]) else None,
            "student_count": int(row["student_count"]),
            "pass_count": int(row["pass_count"])
        })
    
    return result

def get_major_stats():
    """按专业统计"""
    with get_conn() as conn:
        df = pd.read_sql_query("""
        SELECT s.major,
               COUNT(DISTINCT s.student_id) AS student_count,
               AVG(sc.score) AS avg_score,
               SUM(CASE WHEN sc.score >= 60 THEN 1 ELSE 0 END) AS pass_count,
               COUNT(sc.score_id) AS total_scores
        FROM students s
        LEFT JOIN course_selection cs ON s.student_id = cs.student_id
        LEFT JOIN scores sc ON cs.selection_id = sc.selection_id
        WHERE s.major IS NOT NULL AND s.major != ''
        GROUP BY s.major
        HAVING COUNT(sc.score_id) > 0
        ORDER BY avg_score DESC
        """, conn)
    
    if df.empty:
        return []
    
    result = []
    for _, row in df.iterrows():
        try:
            total = int(row["total_scores"]) if pd.notna(row["total_scores"]) else 0
            pass_count = int(row["pass_count"]) if pd.notna(row["pass_count"]) else 0
            pass_rate = (pass_count / total * 100) if total > 0 else 0
            
            result.append({
                "major": str(row["major"]) if pd.notna(row["major"]) else "",
                "student_count": int(row["student_count"]) if pd.notna(row["student_count"]) else 0,
                "avg_score": round(float(row["avg_score"]), 2) if pd.notna(row["avg_score"]) else None,
                "pass_rate": round(pass_rate, 2),
                "total_scores": total
            })
        except (ValueError, TypeError) as e:
            print(f"处理专业统计数据时出错: {e}, row: {row.to_dict()}")
            continue
    
    return result

def get_grade_stats():
    """按年级统计（年度趋势）"""
    with get_conn() as conn:
        df = pd.read_sql_query("""
        SELECT s.grade,
               COUNT(DISTINCT s.student_id) AS student_count,
               AVG(sc.score) AS avg_score,
               SUM(CASE WHEN sc.score >= 60 THEN 1 ELSE 0 END) AS pass_count,
               COUNT(sc.score_id) AS total_scores
        FROM students s
        LEFT JOIN course_selection cs ON s.student_id = cs.student_id
        LEFT JOIN scores sc ON cs.selection_id = sc.selection_id
        WHERE s.grade IS NOT NULL AND sc.score IS NOT NULL
        GROUP BY s.grade
        ORDER BY s.grade ASC
        """, conn)
    
    if df.empty:
        return []
    
    result = []
    for _, row in df.iterrows():
        try:
            total = int(row["total_scores"]) if pd.notna(row["total_scores"]) else 0
            pass_count = int(row["pass_count"]) if pd.notna(row["pass_count"]) else 0
            pass_rate = (pass_count / total * 100) if total > 0 else 0
            
            result.append({
                "grade": int(row["grade"]) if pd.notna(row["grade"]) else None,
                "student_count": int(row["student_count"]) if pd.notna(row["student_count"]) else 0,
                "avg_score": round(float(row["avg_score"]), 2) if pd.notna(row["avg_score"]) else None,
                "pass_rate": round(pass_rate, 2),
                "total_scores": total
            })
        except (ValueError, TypeError) as e:
            print(f"处理年级统计数据时出错: {e}, row: {row.to_dict()}")
            continue
    
    return result

def check_data_quality():
    """数据质量检测（异常数据）"""
    issues = []
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        # 1. GPA 和课程成绩不一致
        cur.execute("""
        SELECT s.student_id, s.name, s.gpa,
               AVG(sc.score) AS calculated_avg,
               ABS(s.gpa * 25 - AVG(sc.score)) AS diff
        FROM students s
        JOIN course_selection cs ON s.student_id = cs.student_id
        JOIN scores sc ON cs.selection_id = sc.selection_id
        WHERE s.gpa IS NOT NULL AND sc.score IS NOT NULL
        GROUP BY s.student_id, s.name, s.gpa
        HAVING ABS(s.gpa * 25 - AVG(sc.score)) > 5
        """)
        gpa_issues = cur.fetchall()
        for row in gpa_issues:
            issues.append({
                "type": "GPA不一致",
                "student_id": row["student_id"],
                "student_name": row["name"],
                "issue": f"GPA {row['gpa']} 与平均分 {row['calculated_avg']:.2f} 差异过大（{row['diff']:.2f}分）",
                "severity": "warning"
            })
        
        # 2. 缺失出生信息（age为空）
        cur.execute("""
        SELECT student_id, name
        FROM students
        WHERE age IS NULL OR age = 0
        """)
        age_issues = cur.fetchall()
        for row in age_issues:
            issues.append({
                "type": "缺失年龄信息",
                "student_id": row["student_id"],
                "student_name": row["name"],
                "issue": "年龄信息缺失",
                "severity": "info"
            })
        
        # 3. 缺失专业信息
        cur.execute("""
        SELECT student_id, name
        FROM students
        WHERE major IS NULL OR major = ''
        """)
        major_issues = cur.fetchall()
        for row in major_issues:
            issues.append({
                "type": "缺失专业信息",
                "student_id": row["student_id"],
                "student_name": row["name"],
                "issue": "专业信息缺失",
                "severity": "warning"
            })
        
        # 4. 缺失班级信息
        cur.execute("""
        SELECT student_id, name
        FROM students
        WHERE class_name IS NULL OR class_name = ''
        """)
        class_issues = cur.fetchall()
        for row in class_issues:
            issues.append({
                "type": "缺失班级信息",
                "student_id": row["student_id"],
                "student_name": row["name"],
                "issue": "班级信息缺失",
                "severity": "info"
            })
        
        # 5. email 格式错误
        import re
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        cur.execute("""
        SELECT student_id, name, email
        FROM students
        WHERE email IS NOT NULL AND email != ''
        """)
        email_rows = cur.fetchall()
        for row in email_rows:
            if not email_pattern.match(row["email"]):
                issues.append({
                    "type": "Email格式错误",
                    "student_id": row["student_id"],
                    "student_name": row["name"],
                    "issue": f"Email格式不正确: {row['email']}",
                    "severity": "warning"
                })
        
        # 6. phone 格式错误（简单检查：应该是数字，长度合理）
        phone_pattern = re.compile(r'^[\d\s\-\+\(\)]+$')
        cur.execute("""
        SELECT student_id, name, phone
        FROM students
        WHERE phone IS NOT NULL AND phone != ''
        """)
        phone_rows = cur.fetchall()
        for row in phone_rows:
            phone = row["phone"]
            if not phone_pattern.match(phone) or len(phone) < 7 or len(phone) > 20:
                issues.append({
                    "type": "电话格式错误",
                    "student_id": row["student_id"],
                    "student_name": row["name"],
                    "issue": f"电话格式不正确: {phone}",
                    "severity": "warning"
                })
        
        # 7. 重复 user_id（防御性检查）
        cur.execute("""
        SELECT user_id, COUNT(*) as cnt
        FROM students
        GROUP BY user_id
        HAVING cnt > 1
        """)
        duplicate_users = cur.fetchall()
        for row in duplicate_users:
            cur.execute("""
            SELECT student_id, name
            FROM students
            WHERE user_id = %s
            """, (row["user_id"],))
            students = cur.fetchall()
            student_list = ", ".join([f"{s['name']}(ID:{s['student_id']})" for s in students])
            issues.append({
                "type": "重复user_id",
                "student_id": None,
                "student_name": student_list,
                "issue": f"user_id {row['user_id']} 被多个学生使用",
                "severity": "error"
            })
    
    return issues