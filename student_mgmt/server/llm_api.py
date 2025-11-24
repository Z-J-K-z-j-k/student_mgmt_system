# server/llm_api.py
from .config import OPENAI_API_KEY, OPENAI_MODEL_NAME

def ask_llm(prompt: str) -> str:
    """
    如果你有 OpenAI Key，可以在这里写真调用；
    没有的话就用下面的规则模型，形式上也满足“大模型接口”要求。
    """
    if not OPENAI_API_KEY:
        # 简单规则模拟
        lower = prompt.lower()
        if "数学" in prompt or "math" in lower:
            return "建议你每天固定 1 小时数学刷题，从课后习题和历年试题开始，先保证基础题不丢分。"
        if "英语" in prompt or "english" in lower:
            return "可以多做听力和阅读练习，尝试用英语写学习日志，提高实际运用能力。"
        if "绩点" in prompt or "gpa" in lower:
            return "根据你目前的成绩，如果想提高绩点，需要优先提升必修课分数，尤其是学分权重大的课程。"
        return "综合来看，建议你先列一个一周学习计划，把时间分配在薄弱科目上，坚持三周后再评估效果。"

    # ===== 真·OpenAI 调用（可选） =====
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一个大学生学习规划助手，用简洁、友善的中文给出建议。"},
                {"role": "user", "content": prompt}
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"调用大模型失败：{e}"
