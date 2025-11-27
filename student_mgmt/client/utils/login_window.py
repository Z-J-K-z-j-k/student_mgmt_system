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
from .window_keeper import keep_window


class LoginWindow(QDialog):
    def __init__(self, api: APIClient, on_login_success):
        super().__init__()
        self.api = api
        self.on_login_success = on_login_success
        self.main_window = None  # 保持主窗口引用，避免被垃圾回收后程序退出
        keep_window(self)  # 确保登录窗口本身在需要时保持引用

        self.setWindowTitle("学生管理系统 - 登录")
        self.setObjectName("LoginDialog")  # 设置objectName用于样式选择
        self.setFixedSize(420, 350)
        # 设置登录窗口背景，确保不受全局样式影响
        self.setStyleSheet("""
            QDialog#LoginDialog {
                background-color: #1f1f1f;
            }
        """)

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
                border: none;
            }
            QFrame#LoginCard QLabel#TitleLabel {
                font-size: 16px;
                color: #1f1f1f;
                font-weight: 600;
                background: transparent;
            }
            QFrame#LoginCard QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
                background-color: #ffffff;
                color: #1f1f1f;
                font-size: 14px;
            }
            QFrame#LoginCard QLineEdit:focus {
                border: 1px solid #3A8DFF;
                background-color: #ffffff;
            }
            QFrame#LoginCard QLineEdit::placeholder {
                color: #999999;
            }
            QFrame#LoginCard QComboBox {
                border: 1px solid #e0e0e0;
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: none;
                padding: 10px;
                background-color: #ffffff;
                color: #1f1f1f;
                font-size: 14px;
            }
            QFrame#LoginCard QComboBox:focus {
                border: 1px solid #3A8DFF;
                border-right: none;
            }
            QFrame#LoginCard QComboBox::drop-down {
                width: 0px;
                border: none;
                subcontrol-origin: padding;
                subcontrol-position: top right;
            }
            QFrame#LoginCard QComboBox::drop-down:open {
                border: none;
            }
            QFrame#LoginCard QComboBox QAbstractItemView {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: #ffffff;
                color: #1f1f1f;
                selection-background-color: #3A8DFF;
                selection-color: #ffffff;
                padding: 4px;
                outline: none;
            }
            QFrame#LoginCard QPushButton#LoginButton {
                background-color: #3A8DFF;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-weight: 600;
                font-size: 14px;
            }
            QFrame#LoginCard QPushButton#LoginButton:hover {
                background-color: #5BA0FF;
            }
            QFrame#LoginCard QPushButton#LoginButton:pressed {
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
        # 确保下拉框可以正常打开
        self.combo_role.setEditable(False)
        
        # 为下拉框添加一个显示"↓"的容器
        from PyQt6.QtWidgets import QHBoxLayout, QWidget
        role_container = QWidget()
        role_layout = QHBoxLayout(role_container)
        role_layout.setContentsMargins(0, 0, 0, 0)
        role_layout.setSpacing(0)
        role_layout.addWidget(self.combo_role, 1)
        
        # 添加箭头标签（可点击）
        arrow_label = QLabel("↓")
        arrow_label.setObjectName("RoleArrow")
        arrow_label.setStyleSheet("""
            QLabel#RoleArrow {
                color: #666666;
                font-size: 18px;
                padding: 0px;
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-left: none;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QLabel#RoleArrow:hover {
                background-color: #e8e8e8;
            }
        """)
        arrow_label.setFixedWidth(35)
        arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_label.setCursor(Qt.CursorShape.PointingHandCursor)  # 设置鼠标指针为手型
        
        # 点击箭头标签时打开下拉框（正确处理事件）
        def on_arrow_click(event):
            # 阻止事件传播，避免影响其他控件
            event.accept()
            # 确保下拉框获得焦点
            self.combo_role.setFocus()
            # 延迟一点打开下拉框，确保焦点设置完成
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(10, self.combo_role.showPopup)
        
        arrow_label.mousePressEvent = on_arrow_click
        role_layout.addWidget(arrow_label)
        
        # 保存箭头标签引用，用于焦点变化时更新样式
        self.arrow_label = arrow_label
        
        # 当QComboBox获得焦点时，更新箭头标签的边框颜色
        def on_focus_in():
            self.arrow_label.setStyleSheet("""
                QLabel#RoleArrow {
                    color: #666666;
                    font-size: 18px;
                    padding: 0px;
                    background-color: #f5f5f5;
                    border: 1px solid #3A8DFF;
                    border-left: none;
                    border-top-right-radius: 6px;
                    border-bottom-right-radius: 6px;
                }
            """)
        
        def on_focus_out():
            self.arrow_label.setStyleSheet("""
                QLabel#RoleArrow {
                    color: #666666;
                    font-size: 18px;
                    padding: 0px;
                    background-color: #f5f5f5;
                    border: 1px solid #e0e0e0;
                    border-left: none;
                    border-top-right-radius: 6px;
                    border-bottom-right-radius: 6px;
                }
            """)
        
        # 使用定时器检查焦点状态（因为QComboBox没有直接的焦点信号）
        from PyQt6.QtCore import QTimer
        self.focus_timer = QTimer()
        self.focus_timer.setSingleShot(False)
        # 检查焦点状态，但避免在下拉框打开时干扰
        def check_focus():
            if not self.combo_role.view().isVisible():  # 如果下拉列表不可见，才更新样式
                if self.combo_role.hasFocus():
                    on_focus_in()
                else:
                    on_focus_out()
        self.focus_timer.timeout.connect(check_focus)
        self.focus_timer.start(100)  # 每100ms检查一次

        form_layout = QVBoxLayout()
        form_layout.setSpacing(14)
        form_layout.addWidget(self.edit_username)
        form_layout.addWidget(self.edit_password)
        form_layout.addWidget(role_container)

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
            # 根据角色先创建主界面（先创建并显示主窗口，避免在关闭登录窗口时触发应用退出）
            user_id = data.get("user_id")
            role = data.get("role")

            if role == "admin":
                from ..admin_main_window import AdminMainWindow
                self.main_window = AdminMainWindow(self.api, user_id)
            elif role == "teacher":
                from ..teacher_main_window import TeacherMainWindow
                self.main_window = TeacherMainWindow(self.api, user_id)
            elif role == "student":
                from ..student_main_window import StudentMainWindow
                self.main_window = StudentMainWindow(self.api, user_id)
            else:
                QMessageBox.warning(self, "错误", f"未知角色：{role}")
                return

            if self.main_window:
                keep_window(self.main_window)
                self.main_window.show()
                self.main_window.raise_()
                # 现在安全地关闭登录窗口
                self.close()
        else:
            QMessageBox.warning(self, "登录失败", data.get("msg", "未知错误"))

