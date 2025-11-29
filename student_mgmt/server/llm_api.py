# server/llm_api.py
import logging
from typing import Optional

import requests

from .config import (
    OPENAI_API_KEY,
    OPENAI_MODEL_NAME,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL_NAME,
    DEEPSEEK_API_URL,
)

LLM_TIMEOUT = 30
logger = logging.getLogger(__name__)


def ask_llm(prompt: str, role: Optional[str] = None) -> str:
    """
    大模型调用入口：
    - 优先调用 DeepSeek API（如果配置了 Key）
    - 其次调用 OpenAI（可选）
    - 都没有时，回退到规则模型
    
    Args:
        prompt: 用户输入的提示词
        role: 用户角色（'student', 'teacher', 'admin'），用于调整 system prompt
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return "请输入具体的问题或需求，我才能更好地帮助你。"

    if DEEPSEEK_API_KEY:
        reply = _ask_deepseek(prompt, role)
        if reply:
            return reply

    if OPENAI_API_KEY:
        reply = _ask_openai(prompt, role)
        if reply:
            return reply

    return _rule_based(prompt)


def _ask_deepseek(prompt: str, role: Optional[str] = None) -> Optional[str]:
    try:
        # 根据角色设置不同的 system prompt
        if role == "admin":
            system_content = (
                "你是一个学生管理系统的智能助手，专门为系统管理员提供支持。"
                "用户的提问会包含【用户背景】部分，其中提供了整个数据库的详细统计信息和数据列表。"
                "请仔细阅读这些背景信息，基于其中的具体数据来回答管理员的问题。"
                "你可以引用具体的统计数据、学生信息、教师信息、课程信息等。"
                "请用专业、准确的中文回答，提供数据洞察、趋势分析和决策建议。"
            )
        elif role == "teacher":
            system_content = (
                "你是一个教学管理助手，帮助教师分析课程教学情况、学生成绩分布等。"
                "用户的提问会包含【用户背景】部分，其中提供了当前登录教师的详细信息，"
                "包括教师基本信息、教授的课程及每门课程的详细统计（选课人数、平均分、及格率等）。"
                "请基于这些具体的背景信息来回答教师的问题，提供针对性的教学建议。"
                "用简洁、友善的中文提供建议，回答不少于两条具体行动建议。"
            )
        else:  # student 或默认
            system_content = (
                "你是一个大学生学习规划助手，帮助学生进行学习规划和选课咨询。"
                "用户的提问会包含【用户背景】部分，其中提供了当前登录学生的详细信息，"
                "包括学生基本信息、GPA、所有课程成绩、成绩统计、薄弱科目等。"
                "请基于这些具体的背景信息来回答学生的问题，提供个性化的学习建议。"
                "用简洁、友善的中文提供建议，回答不少于两条具体行动建议。"
            )
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEEPSEEK_MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {"role": "user", "content": prompt},
            ],
        }
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=LLM_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return "模型没有返回内容，请稍后再试。"
        return choices[0]["message"]["content"].strip()
    except Exception as exc:
        logger.exception("调用 DeepSeek 失败: %s", exc)
        return None


def _ask_openai(prompt: str, role: Optional[str] = None) -> Optional[str]:
    try:
        from openai import OpenAI

        # 根据角色设置不同的 system prompt
        if role == "admin":
            system_content = (
                "你是一个学生管理系统的智能助手，专门为系统管理员提供支持。"
                "用户的提问会包含【用户背景】部分，其中提供了整个数据库的详细统计信息和数据列表。"
                "请仔细阅读这些背景信息，基于其中的具体数据来回答管理员的问题。"
                "你可以引用具体的统计数据、学生信息、教师信息、课程信息等。"
                "请用专业、准确的中文回答，提供数据洞察、趋势分析和决策建议。"
            )
        elif role == "teacher":
            system_content = (
                "你是一个教学管理助手，帮助教师分析课程教学情况、学生成绩分布等。"
                "用户的提问会包含【用户背景】部分，其中提供了当前登录教师的详细信息，"
                "包括教师基本信息、教授的课程及每门课程的详细统计（选课人数、平均分、及格率等）。"
                "请基于这些具体的背景信息来回答教师的问题，提供针对性的教学建议。"
                "用简洁、友善的中文给出建议。"
            )
        else:  # student 或默认
            system_content = (
                "你是一个大学生学习规划助手，帮助学生进行学习规划和选课咨询。"
                "用户的提问会包含【用户背景】部分，其中提供了当前登录学生的详细信息，"
                "包括学生基本信息、GPA、所有课程成绩、成绩统计、薄弱科目等。"
                "请基于这些具体的背景信息来回答学生的问题，提供个性化的学习建议。"
                "用简洁、友善的中文给出建议。"
            )

        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": system_content,
                },
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.exception("调用 OpenAI 失败: %s", exc)
        return None


def _rule_based(prompt: str) -> str:
    lower = prompt.lower()
    if "数学" in prompt or "math" in lower:
        return "建议你每天固定 1 小时数学刷题，从课后习题和历年试题开始，先保证基础题不丢分。"
    if "英语" in prompt or "english" in lower:
        return "可以多做听力和阅读练习，尝试用英语写学习日志，提高实际运用能力。"
    if "绩点" in prompt or "gpa" in lower:
        return "根据你目前的成绩，如果想提高绩点，需要优先提升必修课分数，尤其是学分权重大的课程。"
    return "综合来看，建议你先列一个一周学习计划，把时间分配在薄弱科目上，坚持三周后再评估效果。"
