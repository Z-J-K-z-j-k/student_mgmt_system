# client/admin_main_window.py
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QVBoxLayout
)
from PyQt6.QtCore import Qt

from .pages.user_password_page import UserPasswordPage
from .pages.students_page import StudentsPage
from .pages.teachers_page import TeachersPage
from .pages.courses_page import CoursesPage
from .pages.scores_page import ScoresPage
from .pages.llm_page import LLMPage
from .pages.classrooms_page import ClassroomsPage
from .pages.course_schedule_page import CourseSchedulePage
from .pages.comprehensive_stats_page import ComprehensiveStatsPage
from .utils.api_client import APIClient
from .utils.window_keeper import keep_window


class AdminMainWindow(QMainWindow):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        keep_window(self)
        self.setWindowTitle("学生管理系统 - 管理员")
        self.resize(1200, 720)

        # ---------- 中央区域 ----------
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ============================================================
        # 左侧侧边栏
        # ============================================================
        self.sidebar = QWidget()
        self.sidebar.setObjectName("SideBar")
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(8, 8, 8, 8)
        side_layout.setSpacing(8)

        # 用户信息
        self.lbl_user = QLabel(f"当前用户：{self.api.real_name}（管理员）")
        self.lbl_user.setStyleSheet("color: white; font-weight: bold;")
        side_layout.addWidget(self.lbl_user)

        # 菜单按钮列表
        self.menu_buttons = []
        self.menu_pages = []

        # 添加菜单项
        menu_items = [
            ("🔐 用户密码管理", UserPasswordPage(self.api)),
            ("🧍‍♂️ 学生管理", StudentsPage(self.api, "admin")),
            ("👨‍🏫 教师管理", TeachersPage(self.api, "admin")),
            ("📚 课程管理", CoursesPage(self.api, "admin")),
            ("📝 成绩管理", ScoresPage(self.api, "admin", self.user_id)),
            ("🏫 教室管理", ClassroomsPage(self.api)),
            ("📅 课程安排管理", CourseSchedulePage(self.api)),
            ("📊 综合统计", ComprehensiveStatsPage(self.api)),
            ("🤖 大模型助手", LLMPage(self.api, "admin")),
        ]

        for title, page in menu_items:
            btn = QPushButton(title)
            btn.setObjectName("MenuButton")
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 12px 15px;
                    border: none;
                    border-radius: 6px;
                    background-color: transparent;
                    color: #cfd3dc;
                }
                QPushButton:hover {
                    background-color: #3a3f4a;
                }
                QPushButton:checked {
                    background-color: #3a8dd0;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, idx=len(self.menu_buttons): self.switch_page(idx))
            self.menu_buttons.append(btn)
            self.menu_pages.append(page)
            side_layout.addWidget(btn)

        side_layout.addStretch()

        # 退出按钮
        self.btn_logout = QPushButton("🚪 退出登录")
        self.btn_logout.setObjectName("LogoutButton")
        self.btn_logout.setStyleSheet("""
            QPushButton {
                background-color: #39404d;
                color: #e6e6e6;
                border-radius: 6px;
                padding: 12px;
                height: 40px;
            }
            QPushButton:hover {
                background-color: #4a5363;
            }
            QPushButton:pressed {
                background-color: #3a4352;
            }
        """)
        self.btn_logout.clicked.connect(self.logout)
        side_layout.addWidget(self.btn_logout)

        self.sidebar.setFixedWidth(210)
        root_layout.addWidget(self.sidebar)

        # ============================================================
        # 右侧主区域：StackedWidget
        # ============================================================
        self.stack = QStackedWidget()
        for page in self.menu_pages:
            self.stack.addWidget(page)
        root_layout.addWidget(self.stack, 5)

        # 默认选中第一项
        if self.menu_buttons:
            self.menu_buttons[0].setChecked(True)
            self.stack.setCurrentIndex(0)

        # ============================================================
        # 加载样式表 QSS
        # ============================================================
        qss_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def switch_page(self, index: int):
        """切换页面"""
        for i, btn in enumerate(self.menu_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    def logout(self):
        """退出登录"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认", "确定要退出登录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # 重置API客户端
            self.api.token = None
            self.api.user_id = None
            self.api.role = None
            self.api.real_name = None
            self.close()
            # 重新打开登录窗口
            from .login_window import LoginWindow
            from .utils.api_client import APIClient
            login_win = LoginWindow(APIClient(), None)
            keep_window(login_win)
            login_win.show()

