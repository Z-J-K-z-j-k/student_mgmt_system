# server/config.py

# MySQL 数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "Zjk123456"  # 请修改为你的MySQL密码
MYSQL_DATABASE = "student_mgmt"
MYSQL_CHARSET = "utf8mb4"

# 图表目录
CHART_DIR = "static/charts"

# 大模型相关配置
# 如果没有 DeepSeek / OpenAI Key，可以留空，系统会自动使用 llm_api 中的规则模型
OPENAI_API_KEY = ""
OPENAI_MODEL_NAME = "gpt-3.5-turbo"

DEEPSEEK_API_KEY = "sk-80db776eae9f4bebbcd655d5c63ca462"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
