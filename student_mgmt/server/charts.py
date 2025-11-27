# server/charts.py
import os
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .analysis import load_scores_df, get_major_stats, get_grade_stats, get_course_avg_comparison
from .config import CHART_DIR

# 配置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 确保图表目录路径正确（相对于项目根目录）
if __package__ in (None, ""):
    # 直接运行脚本时，使用项目根目录
    project_root = Path(__file__).resolve().parents[1]
    chart_dir = project_root / CHART_DIR
else:
    # 作为包导入时，使用当前工作目录
    chart_dir = Path(CHART_DIR)
    if not chart_dir.is_absolute():
        chart_dir = Path.cwd() / CHART_DIR

# 确保目录存在
chart_dir.mkdir(parents=True, exist_ok=True)
CHART_DIR_ABS = str(chart_dir)

def generate_score_histogram():
    df = load_scores_df()
    filename = os.path.join(CHART_DIR_ABS, "score_hist.png")
    if df.empty:
        plt.figure()
        plt.text(0.5, 0.5, "暂无成绩数据", ha="center", va="center")
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()
        return filename

    plt.figure()
    plt.hist(df["score"], bins=[0,60,70,80,90,100])
    plt.xlabel("分数")
    plt.ylabel("人数")
    plt.title("成绩分布直方图")
    plt.savefig(filename, bbox_inches="tight")
    plt.close()
    return filename

def generate_major_pie():
    df = load_scores_df()
    filename = os.path.join(CHART_DIR_ABS, "major_pie.png")
    if df.empty:
        plt.figure()
        plt.text(0.5, 0.5, "暂无成绩数据", ha="center", va="center")
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()
        return filename

    counts = df.groupby("major")["student_id"].nunique()
    plt.figure()
    plt.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
    plt.title("各专业学生人数占比")
    plt.savefig(filename, bbox_inches="tight")
    plt.close()
    return filename

def generate_major_avg_bar():
    """生成专业平均分柱状图 - 直接从数据库查询并生成"""
    from .models import get_conn
    
    # 确保目录存在
    Path(CHART_DIR_ABS).mkdir(parents=True, exist_ok=True)
    filename = os.path.join(CHART_DIR_ABS, "major_avg_bar.png")
    
    try:
        # 直接查询数据库
        with get_conn() as conn:
            query = """
            SELECT s.major, AVG(sc.score) as avg_score
            FROM students s
            JOIN scores sc ON s.student_id = sc.student_id
            WHERE s.major IS NOT NULL AND s.major != '' AND sc.score IS NOT NULL
            GROUP BY s.major
            ORDER BY avg_score DESC
            """
            df = pd.read_sql_query(query, conn)
        
        if df.empty or len(df) == 0:
            # 没有数据时生成空图表
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=16)
            plt.axis("off")
            plt.savefig(filename, bbox_inches="tight", dpi=100)
            plt.close()
            return filename
        
        # 提取数据并确保类型正确
        majors = []
        avg_scores = []
        
        for _, row in df.iterrows():
            major = str(row["major"]).strip() if pd.notna(row["major"]) else ""
            if not major:
                continue
            
            # 确保avg_score是数值类型
            try:
                score = float(row["avg_score"]) if pd.notna(row["avg_score"]) else 0.0
            except (ValueError, TypeError):
                score = 0.0
            
            majors.append(major)
            avg_scores.append(score)
        
        if not majors:
            # 没有有效数据时生成空图表
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=16)
            plt.axis("off")
            plt.savefig(filename, bbox_inches="tight", dpi=100)
            plt.close()
            return filename
        
        # 生成图表
        plt.figure(figsize=(10, 6))
        bars = plt.bar(majors, avg_scores, color='#4ecdc4')
        plt.xlabel("专业", fontsize=12)
        plt.ylabel("平均分", fontsize=12)
        plt.title("各专业平均分对比", fontsize=14, fontweight='bold')
        plt.xticks(rotation=45, ha='right')
        plt.grid(axis='y', alpha=0.3)
        
        # 在柱状图上显示数值
        for bar, score in zip(bars, avg_scores):
            if score > 0:
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                        f'{score:.1f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(filename, bbox_inches="tight", dpi=100)
        plt.close()
        
        return filename
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"生成专业图表失败: {error_detail}")
        # 生成错误提示图表
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, f"生成图表失败\n{str(e)}", ha="center", va="center", fontsize=12)
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight", dpi=100)
        plt.close()
        return filename

def generate_grade_trend():
    """生成年级趋势折线图（只显示平均分）- 直接从数据库查询并生成"""
    from .models import get_conn
    
    # 确保目录存在
    Path(CHART_DIR_ABS).mkdir(parents=True, exist_ok=True)
    filename = os.path.join(CHART_DIR_ABS, "grade_trend.png")
    
    try:
        # 直接查询数据库
        with get_conn() as conn:
            query = """
            SELECT s.grade, AVG(sc.score) as avg_score
            FROM students s
            JOIN scores sc ON s.student_id = sc.student_id
            WHERE s.grade IS NOT NULL AND sc.score IS NOT NULL
            GROUP BY s.grade
            ORDER BY s.grade ASC
            """
            df = pd.read_sql_query(query, conn)
        
        if df.empty or len(df) == 0:
            # 没有数据时生成空图表
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=16)
            plt.axis("off")
            plt.savefig(filename, bbox_inches="tight", dpi=100)
            plt.close()
            return filename
        
        # 提取数据并确保类型正确
        grades = []
        avg_scores = []
        
        for _, row in df.iterrows():
            # 确保grade是整数类型
            try:
                grade_val = row["grade"]
                if pd.isna(grade_val):
                    continue
                # 尝试转换为整数
                if isinstance(grade_val, str):
                    # 如果是字符串，尝试转换
                    if grade_val.strip().isdigit():
                        grade_val = int(grade_val.strip())
                    else:
                        continue  # 跳过非数字字符串
                else:
                    grade_val = int(float(grade_val))  # 先转float再转int，处理小数
            except (ValueError, TypeError):
                continue  # 跳过无法转换的值
            
            # 确保avg_score是数值类型
            try:
                score = float(row["avg_score"]) if pd.notna(row["avg_score"]) else 0.0
            except (ValueError, TypeError):
                score = 0.0
            
            grades.append(grade_val)
            avg_scores.append(score)
        
        if not grades:
            # 没有有效数据时生成空图表
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=16)
            plt.axis("off")
            plt.savefig(filename, bbox_inches="tight", dpi=100)
            plt.close()
            return filename
        
        # 按年级排序
        sorted_data = sorted(zip(grades, avg_scores))
        grades, avg_scores = zip(*sorted_data) if sorted_data else ([], [])
        grades = list(grades)
        avg_scores = list(avg_scores)
        
        # 将年级转换为中文标签
        grade_labels = []
        for grade in grades:
            if grade == 1:
                grade_labels.append("大一")
            elif grade == 2:
                grade_labels.append("大二")
            elif grade == 3:
                grade_labels.append("大三")
            elif grade == 4:
                grade_labels.append("大四")
            else:
                grade_labels.append(f"{grade}年级")
        
        # 生成图表
        plt.figure(figsize=(10, 6))
        plt.plot(grades, avg_scores, marker='o', color='#2196F3', linewidth=2, markersize=8)
        plt.xlabel("年级", fontsize=12)
        plt.ylabel("平均分", fontsize=12)
        plt.title("各年级平均分趋势", fontsize=14, fontweight='bold')
        plt.xticks(grades, grade_labels)
        plt.grid(True, alpha=0.3)
        
        # 添加数值标签
        for grade, score in zip(grades, avg_scores):
            if score > 0:
                plt.text(grade, score + 1, f'{score:.1f}', ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        plt.savefig(filename, bbox_inches="tight", dpi=100)
        plt.close()
        
        return filename
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"生成年级图表失败: {error_detail}")
        # 生成错误提示图表
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, f"生成图表失败\n{str(e)}", ha="center", va="center", fontsize=12)
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight", dpi=100)
        plt.close()
        return filename

def generate_course_comparison():
    """生成课程平均分对比图"""
    stats = get_course_avg_comparison()
    filename = os.path.join(CHART_DIR_ABS, "course_comparison.png")
    
    if not stats:
        plt.figure()
        plt.text(0.5, 0.5, "暂无数据", ha="center", va="center")
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()
        return filename
    
    # 只显示前15门课程，避免图表过于拥挤
    stats = stats[:15]
    course_names = [s["course_name"] for s in stats]
    avg_scores = [s["avg_score"] if s["avg_score"] else 0 for s in stats]
    
    plt.figure(figsize=(12, 6))
    bars = plt.barh(range(len(course_names)), avg_scores, color='#FF6B6B')
    plt.yticks(range(len(course_names)), course_names)
    plt.xlabel("平均分", fontsize=12)
    plt.ylabel("课程", fontsize=12)
    plt.title("课程平均分对比（前15门）", fontsize=14, fontweight='bold')
    plt.grid(axis='x', alpha=0.3)
    
    # 在柱状图上显示数值
    for i, (bar, score) in enumerate(zip(bars, avg_scores)):
        if score > 0:
            plt.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    f'{score:.1f}', ha='left', va='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(filename, bbox_inches="tight", dpi=100)
    plt.close()
    return filename

def generate_score_distribution_pie():
    """生成分数分布饼图"""
    df = load_scores_df()
    filename = os.path.join(CHART_DIR_ABS, "score_distribution_pie.png")
    
    if df.empty:
        plt.figure()
        plt.text(0.5, 0.5, "暂无成绩数据", ha="center", va="center")
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()
        return filename
    
    df_valid = df[df["score"].notna()]
    if df_valid.empty:
        plt.figure()
        plt.text(0.5, 0.5, "暂无有效成绩", ha="center", va="center")
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()
        return filename
    
    # 分段统计
    bins = [0, 60, 70, 80, 90, 100]
    labels = ["0-59分", "60-69分", "70-79分", "80-89分", "90-100分"]
    cut = pd.cut(df_valid["score"], bins=bins, labels=labels, include_lowest=True)
    counts = cut.value_counts()
    
    colors = ['#ff6b6b', '#ffd93d', '#6bcf7f', '#4ecdc4', '#45b7d1']
    plt.figure(figsize=(8, 8))
    plt.pie(counts.values, labels=counts.index, autopct='%1.1f%%', colors=colors, startangle=90)
    plt.title("全校成绩分布", fontsize=14, fontweight='bold')
    plt.savefig(filename, bbox_inches="tight", dpi=100)
    plt.close()
    return filename
