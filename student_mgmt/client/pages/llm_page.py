# client/pages/llm_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel
)
from PyQt6.QtCore import Qt
from ..utils.api_client import APIClient

class LLMPage(QWidget):
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api

        layout = QVBoxLayout(self)

        self.lbl_info = QLabel("学习规划 / 选课咨询助手（大模型接口）")
        layout.addWidget(self.lbl_info)

        self.text_history = QTextEdit()
        self.text_history.setReadOnly(True)
        layout.addWidget(self.text_history)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("请在这里输入你的问题，例如：\n我数学 60 分、英语 90 分，该怎么安排复习？")
        self.text_input.setFixedHeight(120)
        layout.addWidget(self.text_input)

        self.btn_send = QPushButton("发送")
        self.btn_send.clicked.connect(self.send_msg)
        layout.addWidget(self.btn_send, alignment=Qt.AlignmentFlag.AlignRight)

    def append(self, who, text):
        self.text_history.append(f"<b>{who}:</b> {text}")

    def send_msg(self):
        prompt = self.text_input.toPlainText().strip()
        if not prompt:
            return
        self.append("我", prompt)
        self.text_input.clear()

        resp = self.api.post("/api/llm_chat", json={"prompt": prompt})
        data = resp.json()
        reply = data.get("reply", "（没有收到回复）")
        self.append("助手", reply)
