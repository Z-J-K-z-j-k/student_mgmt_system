# server/charts.py
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analysis import load_scores_df
from .config import CHART_DIR

Path(CHART_DIR).mkdir(parents=True, exist_ok=True)

def generate_score_histogram():
    df = load_scores_df()
    filename = os.path.join(CHART_DIR, "score_hist.png")
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
    filename = os.path.join(CHART_DIR, "major_pie.png")
    if df.empty:
        plt.figure()
        plt.text(0.5, 0.5, "暂无成绩数据", ha="center", va="center")
        plt.axis("off")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()
        return filename

    counts = df.groupby("major")["student_no"].nunique()
    plt.figure()
    plt.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
    plt.title("各专业学生人数占比")
    plt.savefig(filename, bbox_inches="tight")
    plt.close()
    return filename
