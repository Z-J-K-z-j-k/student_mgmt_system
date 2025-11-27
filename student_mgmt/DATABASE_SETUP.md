# 数据库配置说明

## MySQL 数据库连接配置

本项目已从 SQLite 迁移到 MySQL 数据库。请按照以下步骤配置数据库连接。

### 1. 安装 MySQL

确保你的系统已安装 MySQL 服务器。如果没有，请访问 [MySQL 官网](https://dev.mysql.com/downloads/mysql/) 下载并安装。

### 2. 安装 Python 依赖

确保已安装 `pymysql` 驱动：

```bash
pip install -r requirements.txt
```

### 3. 配置数据库连接

编辑 `student_mgmt/server/config.py` 文件，修改以下配置：

```python
# MySQL 数据库配置
MYSQL_HOST = "localhost"          # MySQL 服务器地址
MYSQL_PORT = 3306                 # MySQL 端口（默认 3306）
MYSQL_USER = "root"               # MySQL 用户名
MYSQL_PASSWORD = "你的密码"        # MySQL 密码（请修改）
MYSQL_DATABASE = "student_mgmt"   # 数据库名称
MYSQL_CHARSET = "utf8mb4"         # 字符集
```

**重要：** 请将 `MYSQL_PASSWORD` 修改为你的 MySQL root 密码。

### 4. 初始化数据库

运行以下命令初始化数据库和表结构：

```bash
cd student_mgmt/server
python -m db_init
```

或者直接运行：

```bash
python student_mgmt/server/db_init.py
```

这个脚本会：
1. 自动创建数据库（如果不存在）
2. 从 `student_mgmt/sql/create_table.sql` 读取并执行建表语句
3. 插入示例数据（管理员、教师、学生等）

### 5. 验证连接

启动服务器测试连接：

```bash
python student_mgmt/server/app.py
```

如果看到服务器正常启动，说明数据库连接成功。

## 数据库表结构

数据库表结构定义在 `student_mgmt/sql/create_table.sql` 文件中，包括：

- `users` - 用户表（登录账号 + 权限）
- `students` - 学生信息表
- `teachers` - 教师信息表
- `courses` - 课程信息表
- `scores` - 成绩表
- `audit_log` - 操作日志表
- `crawl_data` - 爬虫数据表
- `llm_logs` - LLM 调用日志表

## 常见问题

### 问题1：连接被拒绝

**错误信息：** `(2003, "Can't connect to MySQL server on 'localhost'")`

**解决方法：**
- 确保 MySQL 服务正在运行
- 检查 `MYSQL_HOST` 和 `MYSQL_PORT` 配置是否正确
- 检查防火墙设置

### 问题2：访问被拒绝

**错误信息：** `(1045, "Access denied for user 'root'@'localhost'")`

**解决方法：**
- 检查 `MYSQL_USER` 和 `MYSQL_PASSWORD` 是否正确
- 确保 MySQL 用户有创建数据库的权限

### 问题3：数据库不存在

**错误信息：** `(1049, "Unknown database 'student_mgmt'")`

**解决方法：**
- 运行 `python student_mgmt/server/db_init.py` 初始化数据库
- 脚本会自动创建数据库

### 问题4：表已存在错误

**解决方法：**
- 这是正常的，`create_table.sql` 中使用了 `DROP TABLE IF EXISTS`
- 如果表已存在，会先删除再创建

## 注意事项

1. **密码安全：** 不要将包含真实密码的 `config.py` 提交到版本控制系统
2. **备份数据：** 定期备份数据库，可以使用 `mysqldump` 命令
3. **并发控制：** MySQL 的 InnoDB 引擎已提供事务和并发控制支持

## 从 SQLite 迁移

如果你之前使用的是 SQLite 数据库，数据不会自动迁移。你需要：

1. 导出 SQLite 数据
2. 转换为 MySQL 格式
3. 导入到新的 MySQL 数据库

或者重新初始化数据库并重新导入数据。

