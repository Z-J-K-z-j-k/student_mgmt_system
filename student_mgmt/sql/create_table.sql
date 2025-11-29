-- 使用数据库
CREATE DATABASE IF NOT EXISTS student_mgmt;
USE student_mgmt;

SET FOREIGN_KEY_CHECKS = 0;

-- ==========================================
-- 1. 用户表（登录账号 + 权限）
-- ==========================================
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,         -- 存哈希（Werkzeug 生成的哈希值可能较长）
    role ENUM('student', 'teacher', 'admin') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

-- ==========================================
-- 2. 学生信息表
-- ==========================================
DROP TABLE IF EXISTS students;
CREATE TABLE students (
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    gender ENUM('male', 'female') NOT NULL,
    age INT,
    major VARCHAR(100),
    grade INT,                               -- 年级（1~4）
    class_name VARCHAR(50),
    phone VARCHAR(20),
    email VARCHAR(100),
    gpa DECIMAL(3,2),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ==========================================
-- 3. 教师信息表
-- ==========================================
DROP TABLE IF EXISTS teachers;
CREATE TABLE teachers (
    teacher_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    department VARCHAR(100),
    title VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    research VARCHAR(255),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ==========================================
-- 4. 课程信息表
-- ==========================================
DROP TABLE IF EXISTS courses;
CREATE TABLE courses (
    course_id INT PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    teacher_id INT,
    credit INT DEFAULT 2,
    semester VARCHAR(20),
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE SET NULL
);

-- ==========================================
-- 9. 学生选课表（核心）
-- ==========================================
DROP TABLE IF EXISTS course_selection;
CREATE TABLE course_selection (
    selection_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    semester VARCHAR(20) NOT NULL,
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,

    UNIQUE KEY uniq_selection (student_id, course_id, semester)
);

-- ==========================================
-- 5. 成绩（选课 + 分数）
-- ==========================================
DROP TABLE IF EXISTS scores;
CREATE TABLE scores (
    score_id INT PRIMARY KEY AUTO_INCREMENT,
    selection_id INT NOT NULL,  
    score FLOAT,                
    exam_date DATE,
    FOREIGN KEY (selection_id) REFERENCES course_selection(selection_id)
        ON DELETE CASCADE
);


-- ==========================================
-- 6. 操作日志
-- ==========================================
DROP TABLE IF EXISTS audit_log;
CREATE TABLE audit_log (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    action VARCHAR(255),
    target_table VARCHAR(50),
    target_id INT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ==========================================
-- 7. 爬虫数据表（数据源获取）
-- ==========================================
DROP TABLE IF EXISTS crawl_data;
CREATE TABLE crawl_data (
    crawl_id INT PRIMARY KEY AUTO_INCREMENT,
    source VARCHAR(100),
    url VARCHAR(255),
    title VARCHAR(255),
    content TEXT,
    raw_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 8. LLM 调用日志
-- ==========================================
DROP TABLE IF EXISTS llm_logs;
CREATE TABLE llm_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    role ENUM('student','teacher','admin'),
    query_text TEXT,
    response_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);



-- ==========================================
-- 11. 教室表（可选但规范）
-- ==========================================
DROP TABLE IF EXISTS classrooms;
CREATE TABLE classrooms (
    classroom_id INT PRIMARY KEY AUTO_INCREMENT,
    building VARCHAR(50),
    room VARCHAR(50),
    capacity INT DEFAULT 60
);



-- ==========================================
-- 10. 课程排课表（课程时间与地点）
-- ==========================================
DROP TABLE IF EXISTS course_schedule;
CREATE TABLE course_schedule (
    schedule_id INT PRIMARY KEY AUTO_INCREMENT,

    course_id INT NOT NULL,
    teacher_id INT NOT NULL,
    semester VARCHAR(20) NOT NULL,

    day_of_week ENUM('Mon','Tue','Wed','Thu','Fri','Sat','Sun') NOT NULL,
    period_start INT NOT NULL,
    period_end INT NOT NULL,

    classroom_id INT,
    weeks VARCHAR(50) NOT NULL, -- 例如 '1-16'

    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id) ON DELETE SET NULL
);


SET FOREIGN_KEY_CHECKS = 1;


