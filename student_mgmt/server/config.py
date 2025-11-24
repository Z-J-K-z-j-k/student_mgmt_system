# server/config.py

DB_PATH = "../student_mgmt.db"   # 相对整个项目根目录
CHART_DIR = "static/charts"

# 大模型相关（如果你没有 Key，就用 llm_api 里的伪模型）
OPENAI_API_KEY = ""      # 可留空
OPENAI_MODEL_NAME = "gpt-3.5-turbo"
