# client/pages/teacher_info_page.py
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt

from ..utils.api_client import APIClient


class TeacherInfoPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.teacher_id = None
        self.is_editing = False

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # 标题 + 操作按钮
        header_layout = QHBoxLayout()
        title = QLabel("👨‍🏫 我的信息")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            """
        )
        self.btn_edit.clicked.connect(self.enter_edit_mode)
        header_layout.addWidget(self.btn_edit)

        self.btn_save = QPushButton("保存")
        self.btn_save.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            """
        )
        self.btn_save.clicked.connect(self.save_changes)
        self.btn_save.setVisible(False)
        header_layout.addWidget(self.btn_save)

        layout.addLayout(header_layout)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.status_label)

        # 信息显示区域
        form = QFormLayout()
        form.setSpacing(15)

        self.lbl_name = QLabel()
        self.lbl_name.setStyleSheet("color: #1f1f1f;")
        self.lbl_username = QLabel()
        self.lbl_username.setStyleSheet("color: #1f1f1f;")
        self.lbl_dept = QLabel()
        self.lbl_dept.setStyleSheet("color: #1f1f1f;")
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("color: #1f1f1f;")

        self.edit_phone = QLineEdit()
        self.edit_phone.setPlaceholderText("请输入电话")
        self.edit_phone.setEnabled(False)
        self.edit_email = QLineEdit()
        self.edit_email.setPlaceholderText("请输入邮箱")
        self.edit_email.setEnabled(False)
        self.edit_research = QTextEdit()
        self.edit_research.setFixedHeight(80)
        self.edit_research.setPlaceholderText("请填写研究方向，最多几句话即可")
        self.edit_research.setReadOnly(True)

        form.addRow("姓名：", self.lbl_name)
        form.addRow("账号：", self.lbl_username)
        form.addRow("学院：", self.lbl_dept)
        form.addRow("职称：", self.lbl_title)
        form.addRow("电话：", self.edit_phone)
        form.addRow("邮箱：", self.edit_email)
        form.addRow("研究方向：", self.edit_research)

        layout.addLayout(form)
        layout.addStretch()

        self.refresh()

    def enter_edit_mode(self):
        self.is_editing = True
        self.btn_edit.setVisible(False)
        self.btn_save.setVisible(True)
        self.edit_phone.setEnabled(True)
        self.edit_email.setEnabled(True)
        self.edit_research.setReadOnly(False)
        self.edit_phone.setFocus()

    def exit_edit_mode(self):
        self.is_editing = False
        self.btn_edit.setVisible(True)
        self.btn_save.setVisible(False)
        self.edit_phone.setEnabled(False)
        self.edit_email.setEnabled(False)
        self.edit_research.setReadOnly(True)

    def refresh(self):
        """刷新教师信息"""
        self.exit_edit_mode()
        self.set_loading(True, "正在获取个人信息…")
        try:
            resp = self.api.get("/api/teacher/profile")
            
            if resp.status_code != 200:
                self.set_loading(False)
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", f"服务器返回错误：{resp.status_code}")
                except:
                    error_msg = f"服务器返回错误：{resp.status_code}"
                QMessageBox.critical(self, "错误", error_msg)
                return
            
            data = resp.json()
        except Exception as e:
            self.set_loading(False)
            QMessageBox.critical(self, "错误", f"获取教师信息失败：{e}")
            return

        self.set_loading(False)

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        info = data.get("data") or {}
        self.teacher_id = info.get("teacher_id")
        self.lbl_name.setText(info.get("name") or "-")
        self.lbl_username.setText(info.get("username") or "-")
        self.lbl_dept.setText(info.get("department") or "-")
        self.lbl_title.setText(info.get("title") or "-")
        self.edit_phone.setText(info.get("phone") or "")
        self.edit_email.setText(info.get("email") or "")
        self.edit_research.setPlainText(info.get("research") or "")

    def save_changes(self):
        if not self.is_editing:
            return

        phone = self.edit_phone.text().strip()
        email = self.edit_email.text().strip()
        research = self.edit_research.toPlainText().strip()

        payload = {
            "phone": phone,
            "email": email,
            "research": research,
        }
        self.set_loading(True, "正在保存…")
        try:
            resp = self.api.put("/api/teacher/profile", json=payload)
            data = resp.json()
        except Exception as e:
            self.set_loading(False)
            QMessageBox.critical(self, "错误", f"保存失败：{e}")
            return

        self.set_loading(False)

        if data.get("status") == "ok":
            QMessageBox.information(self, "成功", "已更新个人信息")
            self.refresh()
        else:
            QMessageBox.warning(self, "错误", data.get("msg", "保存失败"))

    def set_loading(self, loading: bool, text: str = ""):
        if self.is_editing:
            self.btn_save.setEnabled(not loading)
        else:
            self.btn_edit.setEnabled(not loading)
        if loading and text:
            self.status_label.setText(text)
        else:
            self.status_label.clear()

