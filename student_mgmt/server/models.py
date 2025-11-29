# server/models.py
import pymysql
from contextlib import contextmanager
import threading
import queue
import time
from .config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_CHARSET

# 配置 pymysql 以支持字典格式返回结果
pymysql.install_as_MySQLdb()

# ============================================================
# 连接池配置
# ============================================================
# 连接池配置参数
POOL_MIN_SIZE = 2      # 最小连接数
POOL_MAX_SIZE = 20     # 最大连接数
POOL_IDLE_TIMEOUT = 300  # 空闲连接超时时间（秒）
POOL_TIMEOUT = 10      # 获取连接超时时间（秒）

class ConnectionPool:
    """简单的数据库连接池实现"""
    def __init__(self, min_size=2, max_size=20, idle_timeout=300):
        self.min_size = min_size
        self.max_size = max_size
        self.idle_timeout = idle_timeout
        self._pool = queue.Queue(maxsize=max_size)
        self._created = 0
        self._lock = threading.Lock()
        self._connection_info = {
            'host': MYSQL_HOST,
            'port': MYSQL_PORT,
            'user': MYSQL_USER,
            'password': MYSQL_PASSWORD,
            'database': MYSQL_DATABASE,
            'charset': MYSQL_CHARSET,
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': False
        }
        # 预创建最小连接数
        self._initialize_pool()
    
    def _initialize_pool(self):
        """初始化连接池，创建最小连接数"""
        for _ in range(self.min_size):
            conn = self._create_connection()
            if conn:
                self._pool.put((conn, time.time()))
    
    def _create_connection(self):
        """创建新的数据库连接"""
        try:
            conn = pymysql.connect(**self._connection_info)
            self._created += 1
            return conn
        except Exception as e:
            print(f"创建数据库连接失败: {e}")
            return None
    
    def _is_connection_alive(self, conn):
        """检查连接是否存活"""
        try:
            conn.ping(reconnect=False)
            return True
        except:
            return False
    
    def get_connection(self, timeout=POOL_TIMEOUT):
        """从连接池获取连接"""
        try:
            # 尝试从池中获取连接
            conn, last_used = self._pool.get(timeout=timeout)
            
            # 检查连接是否存活或超时
            if not self._is_connection_alive(conn) or (time.time() - last_used) > self.idle_timeout:
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._created -= 1
                conn = self._create_connection()
                if not conn:
                    raise Exception("无法创建数据库连接")
            
            return conn
        except queue.Empty:
            # 池为空，尝试创建新连接
            with self._lock:
                if self._created < self.max_size:
                    conn = self._create_connection()
                    if conn:
                        return conn
            # 达到最大连接数，等待（使用更短的超时时间避免无限等待）
            try:
                conn, _ = self._pool.get(timeout=min(timeout, 5))
                return conn
            except queue.Empty:
                raise Exception(f"无法获取数据库连接：连接池已满（{self._created}/{self.max_size}）")
    
    def release_connection(self, conn):
        """将连接归还到连接池"""
        if conn:
            try:
                # 检查连接是否仍然有效
                if self._is_connection_alive(conn):
                    # 重置连接状态
                    conn.rollback()
                    self._pool.put((conn, time.time()), timeout=1)
                else:
                    # 连接已失效，关闭它
                    try:
                        conn.close()
                    except:
                        pass
                    with self._lock:
                        self._created -= 1
            except queue.Full:
                # 池已满，关闭连接
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._created -= 1

# 全局连接池（延迟初始化）
_db_pool = None
_pool_lock = threading.Lock()

def _init_pool():
    """初始化数据库连接池"""
    global _db_pool
    if _db_pool is None:
        with _pool_lock:
            if _db_pool is None:
                _db_pool = ConnectionPool(
                    min_size=POOL_MIN_SIZE,
                    max_size=POOL_MAX_SIZE,
                    idle_timeout=POOL_IDLE_TIMEOUT
                )
    return _db_pool

def get_pool():
    """获取连接池实例"""
    return _init_pool()

@contextmanager
def get_conn(isolation_level=None):
    """
    获取 MySQL 数据库连接的上下文管理器（使用连接池）
    支持事务自动提交和回滚
    
    Args:
        isolation_level: 事务隔离级别，可选值：
            - 'READ UNCOMMITTED'
            - 'READ COMMITTED'
            - 'REPEATABLE READ' (默认)
            - 'SERIALIZABLE'
    """
    pool = get_pool()
    conn = pool.get_connection()
    
    # 设置事务隔离级别
    if isolation_level:
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level}")
        except Exception as e:
            pool.release_connection(conn)
            raise
    
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.release_connection(conn)

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
            user_id INT NOT NULL,
            name VARCHAR(50) NOT NULL,
            gender ENUM('male', 'female') NOT NULL,
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
            user_id INT NOT NULL,
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
            course_id INT PRIMARY KEY,
            course_name VARCHAR(100) NOT NULL,
            teacher_id INT,
            credit INT DEFAULT 2,
            semester VARCHAR(20),
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 学生选课表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS course_selection (
            selection_id INT PRIMARY KEY AUTO_INCREMENT,
            student_id INT NOT NULL,
            course_id INT NOT NULL,
            semester VARCHAR(20) NOT NULL,
            selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            UNIQUE KEY uniq_selection (student_id, course_id, semester)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 成绩表（通过 selection_id 关联到 course_selection）
        cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            score_id INT PRIMARY KEY AUTO_INCREMENT,
            selection_id INT NOT NULL,
            score FLOAT,
            exam_date DATE,
            FOREIGN KEY (selection_id) REFERENCES course_selection(selection_id) ON DELETE CASCADE
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
        
        # 教室表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS classrooms (
            classroom_id INT PRIMARY KEY AUTO_INCREMENT,
            building VARCHAR(50),
            room VARCHAR(50),
            capacity INT DEFAULT 60
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 课程排课表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS course_schedule (
            schedule_id INT PRIMARY KEY AUTO_INCREMENT,
            course_id INT NOT NULL,
            teacher_id INT NOT NULL,
            semester VARCHAR(20) NOT NULL,
            day_of_week ENUM('Mon','Tue','Wed','Thu','Fri','Sat','Sun') NOT NULL,
            period_start INT NOT NULL,
            period_end INT NOT NULL,
            classroom_id INT,
            weeks VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
            FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        print("✅ 使用默认表结构创建完成")
