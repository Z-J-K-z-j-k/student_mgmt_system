from __future__ import annotations

import requests
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

from .api_client import APIClient


class LoginWindow(QDialog):
    def __init__(self, api: APIClient, on_login_success):
        super().__init__()
        self.api = api
        self.on_login_success = on_login_success

        self.setWindowTitle("学生管理系统 - 登录")
        self.setFixedSize(420, 350)
        self.setStyleSheet("background-color: #1f1f1f;")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._build_card(), alignment=Qt.AlignmentFlag.AlignCenter)

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(360)
        card.setStyleSheet(
            """
            QFrame#LoginCard {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QLabel#TitleLabel {
                font-size: 16px;
                color: #1f1f1f;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit, QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
                background-color: #ffffff;
                color: #1f1f1f;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3A8DFF;
            }
            QComboBox QAbstractItemView {
                border-radius: 6px;
                selection-background-color: #3A8DFF;
                selection-color: #ffffff;
            }
            QPushButton#LoginButton {
                background-color: #3A8DFF;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-weight: 600;
            }
            QPushButton#LoginButton:hover {
                background-color: #5BA0FF;
            }
            QPushButton#LoginButton:pressed {
                background-color: #2F74D0;
            }
            """
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        title = QLabel("请输入用户名、密码，并选择身份：")
        title.setObjectName("TitleLabel")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.edit_username = QLineEdit()
        self.edit_username.setPlaceholderText("用户名")

        self.edit_password = QLineEdit()
        self.edit_password.setPlaceholderText("密码")
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.combo_role = QComboBox()
        self.combo_role.addItems(["admin", "teacher", "student"])

        form_layout = QVBoxLayout()
        form_layout.setSpacing(14)
        form_layout.addWidget(self.edit_username)
        form_layout.addWidget(self.edit_password)
        form_layout.addWidget(self.combo_role)

        layout.addLayout(form_layout)

        self.btn_login = QPushButton("登录")
        self.btn_login.setObjectName("LoginButton")
        self.btn_login.clicked.connect(self.do_login)
        layout.addWidget(self.btn_login)

        return card

    def get_login_info(self) -> tuple[str, str, str]:
        username = self.edit_username.text().strip()
        password = self.edit_password.text().strip()
        role = self.combo_role.currentText()
        return username, password, role

    def do_login(self):
        username, password, role = self.get_login_info()
        if not username or not password:
            QMessageBox.warning(self, "错误", "用户名和密码不能为空")
            return

        try:
            data = self.api.login(username, password, role)
        except requests.exceptions.RequestException as exc:
            QMessageBox.critical(self, "网络错误", f"无法连接服务器：{exc}")
            return

        if data.get("status") == "ok":
            QMessageBox.information(self, "成功", f"欢迎 {data['real_name']}（{data['role']}）")
            if callable(self.on_login_success):
                self.on_login_success()
        else:
            QMessageBox.warning(self, "登录失败", data.get("msg", "未知错误"))

