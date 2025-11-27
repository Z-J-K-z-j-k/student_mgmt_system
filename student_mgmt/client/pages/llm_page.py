# client/pages/llm_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import importlib

markdown_module = None
try:
    markdown_module = importlib.import_module("markdown")
    render_markdown = markdown_module.markdown
except ImportError:  # pragma: no cover
    def render_markdown(text, extensions=None):
        return text.replace("\n", "<br>")

from ..utils.api_client import APIClient


class LLMWorker(QThread):
    success = pyqtSignal(str)
    failure = pyqtSignal(str)

    def __init__(self, api: APIClient, prompt: str, parent=None):
        super().__init__(parent)
        self.api = api
        self.prompt = prompt

    def run(self):
        try:
            # LLM请求需要更长的超时时间（60秒）
            resp = self.api.post("/api/llm_chat", json={"prompt": self.prompt}, timeout=60)
            if resp.status_code >= 400:
                try:
                    message = resp.json().get("msg", "服务器返回错误")
                except Exception:
                    message = resp.text or "服务器返回错误"
                raise ValueError(message)
            data = resp.json()
            if data.get("status") != "ok":
                raise ValueError(data.get("msg", "调用失败"))
            reply = data.get("reply", "（没有收到回复）")
            self.success.emit(reply)
        except Exception as exc:
            self.failure.emit(str(exc))


class LLMPage(QWidget):
    def __init__(self, api: APIClient, role: str = "student"):
        super().__init__()
        self.api = api
        self.role = role
        self.worker = None
        self._has_history_content = False
        self._body_font = "font-size:16px; line-height:1.4;"

        layout = QVBoxLayout(self)

        # 根据角色显示不同的标题
        if role == "admin":
            title = "🤖 系统管理助手（基于全数据库信息）"
            placeholder = "请在这里输入你的问题，例如：\n当前学生成绩分布情况如何？\n哪个专业的平均GPA最高？\n哪些课程需要重点关注？"
        elif role == "teacher":
            title = "👨‍🏫 教学管理助手（大模型接口）"
            placeholder = "请在这里输入你的问题，例如：\n我的课程学生成绩如何？\n如何提高课程通过率？"
        else:
            title = "学习规划 / 选课咨询助手（大模型接口）"
            placeholder = "请在这里输入你的问题，例如：\n我数学 60 分、英语 90 分，该怎么安排复习？"

        self.lbl_info = QLabel(title)
        self.lbl_info.setStyleSheet("font-size:18px; font-weight:bold;")
        layout.addWidget(self.lbl_info)

        self.text_history = QTextEdit()
        self.text_history.setReadOnly(True)
        self.text_history.setStyleSheet(self._body_font)
        layout.addWidget(self.text_history)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText(placeholder)
        self.text_input.setFixedHeight(120)
        self.text_input.setStyleSheet(self._body_font)
        layout.addWidget(self.text_input)

        controls_layout = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #888888; " + self._body_font)
        self.lbl_status.hide()
        controls_layout.addWidget(self.lbl_status)
        controls_layout.addStretch()

        self.btn_send = QPushButton("发送")
        self.btn_send.setStyleSheet("font-size:16px; min-width:88px; padding:6px 18px;")
        self.btn_send.clicked.connect(self.send_msg)
        controls_layout.addWidget(self.btn_send)
        layout.addLayout(controls_layout)

        self.load_history()

    def append(self, who, text, is_markdown=False):
        if not self._has_history_content:
            self.text_history.clear()
            self._has_history_content = True
        if is_markdown:
            html = render_markdown(text, extensions=["extra"])
            content = f"<b>{who}:</b><div class='llm-reply'>{html}</div>"
        else:
            safe = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            content = f"<b>{who}:</b> {safe}"
        self.text_history.append(content)

    def set_busy(self, busy: bool):
        self.btn_send.setEnabled(not busy)
        if busy:
            self.lbl_status.setText("正在思考…")
            self.lbl_status.show()
        else:
            self.lbl_status.hide()
            self.lbl_status.clear()

    def send_msg(self):
        prompt = self.text_input.toPlainText().strip()
        if not prompt:
            return
        self.append("我", prompt)
        self.text_input.clear()
        self.set_busy(True)

        self.worker = LLMWorker(self.api, prompt, self)
        self.worker.success.connect(self.handle_success)
        self.worker.failure.connect(self.handle_failure)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def handle_success(self, reply: str):
        self.append("助手", reply, is_markdown=True)

    def handle_failure(self, err: str):
        self.append("系统", f"请求失败：{err}")

    def on_worker_finished(self):
        self.set_busy(False)
        self.worker = None

    def load_history(self):
        try:
            resp = self.api.get("/api/llm_logs", params={"limit": 20})
            data = resp.json()
            if data.get("status") != "ok":
                self.text_history.setPlainText(data.get("msg", "无法获取历史记录"))
                self._has_history_content = False
                return
            logs = data.get("data", [])
            if not logs:
                self.text_history.setPlainText("暂无历史提问，试着问问我吧～")
                self._has_history_content = False
                return
            self.text_history.clear()
            for item in reversed(logs):
                ts = item.get("created_at", "")
                query = item.get("query_text", "")
                reply = item.get("response_summary", "")
                if ts:
                    self.text_history.append(f'<span style="color:#9ba0ab;">{ts}</span>')
                if query:
                    self.append("我", query)
                if reply:
                    self.append("助手", reply, is_markdown=True)
                self.text_history.append("<hr>")
            self._has_history_content = True
        except Exception:
            # 历史记录失败时静默处理，避免阻塞页面
            pass
