# server/models.py
import pymysql
from contextlib import contextmanager
from .config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_CHARSET

# 配置 pymysql 以支持字典格式返回结果
pymysql.install_as_MySQLdb()

@contextmanager
def get_conn():
    """
    获取 MySQL 数据库连接的上下文管理器
    支持事务自动提交和回滚
    """
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset=MYSQL_CHARSET,
        cursorclass=pymysql.cursors.DictCursor,  # 返回字典格式
        autocommit=False  # 手动控制事务
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def create_database_if_not_exists():
    """
    创建数据库（如果不存在）
    """
    from .config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    
    # 连接到 MySQL 服务器（不指定数据库）
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset='utf8mb4'
    )
    try:
        cur = conn.cursor()
        # 创建数据库（如果不存在）
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        print(f"✅ 数据库 {MYSQL_DATABASE} 已准备就绪")
    finally:
        conn.close()

def init_db():
    """
    从 SQL 文件初始化数据库
    只创建不存在的表，不会删除现有表和数据
    """
    import os
    import re
    from pathlib import Path
    
    # 确保数据库存在
    create_database_if_not_exists()
    
    # 获取 SQL 文件路径
    sql_file = Path(__file__).parent.parent / "sql" / "create_table.sql"
    
    if not sql_file.exists():
        print(f"⚠ 警告：SQL 文件不存在: {sql_file}")
        print("将使用默认表结构创建...")
        create_tables_default()
        return
    
    # 读取 SQL 文件
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # 改进的 SQL 解析：移除注释，按分号分割
    lines = sql_content.split('\n')
    cleaned_lines = []
    for line in lines:
        # 移除行尾注释（但保留字符串中的 --）
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.startswith('#'):
            continue
        # 简单处理：如果行中有 -- 且不在引号中，移除注释部分
        if '--' in line:
            # 简单检查：如果 -- 前有引号，可能是字符串中的内容
            comment_pos = line.find('--')
            if comment_pos > 0:
                before_comment = line[:comment_pos]
                # 检查引号数量（简单判断）
                quote_count = before_comment.count("'") + before_comment.count('"')
                if quote_count % 2 == 0:  # 偶数个引号，说明不在字符串中
                    line = before_comment
        cleaned_lines.append(line)
    
    # 合并为完整 SQL，然后按分号分割
    full_sql = '\n'.join(cleaned_lines)
    # 按分号分割语句
    statements = [s.strip() for s in full_sql.split(';') if s.strip()]
    
    # 执行 SQL 语句
    with get_conn() as conn:
        cur = conn.cursor()
        for sql in statements:
            # 跳过 CREATE DATABASE 和 USE 语句
            if 'CREATE DATABASE' in sql.upper() or sql.upper().strip().startswith('USE '):
                continue
            # 跳过 DROP TABLE 语句（不删除现有表）
            if 'DROP TABLE' in sql.upper():
                print(f"⏭ 跳过: DROP TABLE 语句（保留现有表）")
                continue
            # 将 CREATE TABLE 改为 CREATE TABLE IF NOT EXISTS
            if 'CREATE TABLE' in sql.upper() and 'IF NOT EXISTS' not in sql.upper():
                # 替换 CREATE TABLE 为 CREATE TABLE IF NOT EXISTS
                sql = re.sub(r'CREATE TABLE\s+', 'CREATE TABLE IF NOT EXISTS ', sql, flags=re.IGNORECASE)
            try:
                cur.execute(sql)
                # 只显示前50个字符
                preview = sql[:50].replace('\n', ' ').replace('\r', ' ')
                print(f"✅ 执行: {preview}...")
            except Exception as e:
                # 如果表已存在，这是正常的，不报错
                if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                    preview = sql[:50].replace('\n', ' ').replace('\r', ' ')
                    print(f"ℹ 表已存在，跳过: {preview}...")
                else:
                    preview = sql[:100].replace('\n', ' ').replace('\r', ' ')
                    print(f"⚠ 执行 SQL 时出错: {e}")
                    print(f"   SQL: {preview}...")
    
    print("✅ 数据库表初始化完成（只创建不存在的表，保留现有数据）")

def create_tables_default():
    """
    默认表结构（如果 SQL 文件不存在时使用）
    注意：这个结构与 create_table.sql 中的结构对应
    """
    with get_conn() as conn:
        cur = conn.cursor()
        
        # 用户表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role ENUM('student', 'teacher', 'admin') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 学生表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            name VARCHAR(50) NOT NULL,
            gender ENUM('male', 'female'),
            age INT,
            major VARCHAR(100),
            grade INT,
            class_name VARCHAR(50),
            phone VARCHAR(20),
            email VARCHAR(100),
            gpa DECIMAL(3,2),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 教师表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            name VARCHAR(50) NOT NULL,
            department VARCHAR(100),
            title VARCHAR(100),
            phone VARCHAR(20),
            email VARCHAR(100),
            research VARCHAR(255),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 课程表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            course_id INT PRIMARY KEY AUTO_INCREMENT,
            course_name VARCHAR(100) NOT NULL,
            teacher_id INT,
            credit INT DEFAULT 2,
            semester VARCHAR(20),
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 成绩表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            score_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT NOT NULL,
            course_id INT NOT NULL,
            score FLOAT,
            exam_date DATE,
            UNIQUE KEY uniq_student_course (student_id, course_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 操作日志表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            action VARCHAR(255),
            target_table VARCHAR(50),
            target_id INT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 爬虫数据表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS crawl_data (
            crawl_id INT PRIMARY KEY AUTO_INCREMENT,
            source VARCHAR(100),
            url VARCHAR(255),
            title VARCHAR(255),
            content TEXT,
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # LLM 日志表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS llm_logs (
            log_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            role ENUM('student','teacher','admin'),
            query_text TEXT,
            response_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        print("✅ 使用默认表结构创建完成")
