# server/crawler.py
import random
import requests
from bs4 import BeautifulSoup
from .models import get_conn

def crawl_dummy_students():
    """
    示例：从一个公开网页抓一些名字（你可以换成学校新闻等），
    然后生成假学生写入数据库。
    """
    url = "https://www.renmingmingzi.com/100gehaotingdexingming.html"  # 只是个示例网站
    try:
        resp = requests.get(url, timeout=5)
        resp.encoding = resp.apparent_encoding
    except Exception as e:
        print("⚠ 爬取失败：", e)
        return 0

    soup = BeautifulSoup(resp.text, "html.parser")
    names = [tag.get_text(strip=True) for tag in soup.find_all("p")][:30]
    majors = ["计算机", "人工智能", "通信工程", "软件工程"]
    classes = ["1班", "2班", "3班"]

    added = 0
    with get_conn() as conn:
        cur = conn.cursor()
        for i, name in enumerate(names):
            sno = f"2024{200+i:03d}"
            gender = random.choice(["男", "女"])
            major = random.choice(majors)
            class_name = major + random.choice(classes)
            try:
                cur.execute("""
                INSERT INTO students (student_no, name, gender, major, class_name)
                VALUES (?, ?, ?, ?, ?)
                """, (sno, name, gender, major, class_name))
                added += 1
            except Exception:
                conn.rollback()
    print(f"✅ 爬虫导入学生 {added} 条")
    return added

if __name__ == "__main__":
    crawl_dummy_students()
