# server/models.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .config import DB_PATH

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """创建所有表"""
    with get_conn() as conn:
        cur = conn.cursor()
        # 用户表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin','teacher','student')),
            real_name TEXT
        );
        """)

        # 学生表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            gender TEXT,
            major TEXT,
            class_name TEXT,
            phone TEXT,
            email TEXT
        );
        """)

        # 教师表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            dept TEXT,
            title TEXT,
            phone TEXT,
            email TEXT
        );
        """)

        # 课程表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            teacher_id INTEGER,
            credit REAL,
            term TEXT,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );
        """)

        # 选课 / 成绩表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            score REAL,
            term TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        );
        """)

