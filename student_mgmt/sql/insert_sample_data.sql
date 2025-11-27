-- 示例数据插入脚本
-- 使用前请确保数据库和表已经创建
USE student_mgmt;

-- ==========================================
-- 1. 插入用户（必须先插入用户，因为学生和教师表有外键）
-- ==========================================
-- 注意：password 字段存储的是哈希值，这里使用简单的示例
-- 实际使用时应该使用 Werkzeug 的 generate_password_hash 生成
INSERT INTO users (username, password, role) VALUES
('student02', 'pbkdf2:sha256:600000$...', 'student'),  -- 密码：123456 的哈希值
('student03', 'pbkdf2:sha256:600000$...', 'student'),
('teacher02', 'pbkdf2:sha256:600000$...', 'teacher'),
('teacher03', 'pbkdf2:sha256:600000$...', 'teacher');

-- 或者使用 Python 生成密码哈希后插入：
-- from werkzeug.security import generate_password_hash
-- password_hash = generate_password_hash('123456')
-- 然后使用 password_hash 的值插入

-- ==========================================
-- 2. 插入学生（需要先有对应的 user_id）
-- ==========================================
-- 假设 user_id=4 是 student02, user_id=5 是 student03
INSERT INTO students (user_id, name, gender, age, major, grade, class_name, phone, email, gpa) VALUES
(4, '赵六', 'male', 20, '软件工程', 2, '软工1班', '13800000004', 'zl@example.com', 3.6),
(5, '孙七', 'female', 19, '数据科学', 1, '数据1班', '13800000005', 'sq@example.com', 3.9);

-- 或者先查询 user_id：
-- INSERT INTO students (user_id, name, gender, age, major, grade, class_name, phone, email, gpa)
-- SELECT user_id, '赵六', 'male', 20, '软件工程', 2, '软工1班', '13800000004', 'zl@example.com', 3.6
-- FROM users WHERE username = 'student02';

-- ==========================================
-- 3. 插入教师（需要先有对应的 user_id）
-- ==========================================
-- 假设 user_id=6 是 teacher02, user_id=7 是 teacher03
INSERT INTO teachers (user_id, name, department, title, phone, email, research) VALUES
(6, '周老师', '计算机学院', '教授', '13900000003', 'zhou@example.com', '深度学习'),
(7, '吴老师', '计算机学院', '副教授', '13900000004', 'wu@example.com', '计算机视觉');

-- ==========================================
-- 4. 插入课程（需要先有教师）
-- ==========================================
-- 假设 teacher_id=3 是周老师, teacher_id=4 是吴老师
INSERT INTO courses (course_name, teacher_id, credit, semester) VALUES
('数据结构', 3, 4, '2024-秋'),
('操作系统', 4, 3, '2024-秋'),
('计算机网络', 3, 3, '2024-秋');

-- ==========================================
-- 5. 插入成绩（需要先有学生和课程）
-- ==========================================
-- 假设 student_id=4 是赵六, student_id=5 是孙七
-- course_id=3 是数据结构, course_id=4 是操作系统, course_id=5 是计算机网络
INSERT INTO scores (student_id, course_id, score, exam_date) VALUES
(4, 3, 88.5, '2024-12-15'),
(4, 4, 92.0, '2024-12-20'),
(5, 3, 95.0, '2024-12-15'),
(5, 5, 89.5, '2024-12-25');

-- ==========================================
-- 完整示例：插入一个完整的学生记录（包含用户、学生信息、选课和成绩）
-- ==========================================
-- 步骤1：插入用户
INSERT INTO users (username, password, role) 
VALUES ('student04', 'pbkdf2:sha256:600000$...', 'student');

-- 步骤2：获取刚插入的 user_id（在 MySQL 中可以使用 LAST_INSERT_ID()）
SET @new_user_id = LAST_INSERT_ID();

-- 步骤3：插入学生信息
INSERT INTO students (user_id, name, gender, age, major, grade, class_name, phone, email, gpa)
VALUES (@new_user_id, '钱八', 'male', 21, '人工智能', 3, 'AI2班', '13800000006', 'qb@example.com', 3.7);

-- 步骤4：获取刚插入的 student_id
SET @new_student_id = LAST_INSERT_ID();

-- 步骤5：为该学生添加成绩（假设 course_id=3 是数据结构）
INSERT INTO scores (student_id, course_id, score, exam_date)
VALUES (@new_student_id, 3, 85.0, '2024-12-15');

-- ==========================================
-- 查询验证
-- ==========================================
-- 查看所有学生
SELECT * FROM students;

-- 查看所有课程
SELECT * FROM courses;

-- 查看所有成绩
SELECT s.name AS student_name, c.course_name, sc.score, sc.exam_date
FROM scores sc
JOIN students s ON sc.student_id = s.student_id
JOIN courses c ON sc.course_id = c.course_id;

