# client/main_window.py
import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QLabel, QPushButton, QVBoxLayout
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from .pages.students_page import StudentsPage
from .pages.teachers_page import TeachersPage
from .pages.courses_page import CoursesPage
from .pages.scores_page import ScoresPage
from .pages.stats_page import StatsPage
from .pages.llm_page import LLMPage
from .utils.api_client import APIClient


class MainWindow(QMainWindow):
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api
        self.setWindowTitle("学生管理系统")
        self.resize(1200, 720)

        # ---------- 中央区域 ----------
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)

        # ============================================================
        # 左侧侧边栏
        # ============================================================
        self.sidebar = QWidget()
        self.sidebar.setObjectName("SideBar")
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(8, 8, 8, 8)

        # 用户信息
        self.lbl_user = QLabel(f"当前用户：{self.api.real_name}（{self.api.role}）")
        self.lbl_user.setStyleSheet("color: white;")
        side_layout.addWidget(self.lbl_user)

        # 菜单列表
        self.menu = QListWidget()
        self.menu.setObjectName("MenuList")
        self.menu.setSpacing(4)
        side_layout.addWidget(self.menu, 1)

        # 退出按钮
        self.btn_logout = QPushButton("退出登录")
        self.btn_logout.setIcon(QIcon(r"student_mgmt\client\resources\icons\exit.svg"))
        side_layout.addWidget(self.btn_logout)

        self.sidebar.setFixedWidth(210)
        root_layout.addWidget(self.sidebar)

        # ============================================================
        # 右侧主区域：StackedWidget
        # ============================================================
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 5)

        # 添加菜单和页面
        self.add_page("学生管理",
                      r"student_mgmt\client\resources\icons\student.svg",
                      StudentsPage(self.api, self.api.role))

        self.add_page("教师管理",
                      r"student_mgmt\client\resources\icons\teacher.svg",
                      TeachersPage(self.api, self.api.role))

        self.add_page("课程管理",
                      r"student_mgmt\client\resources\icons\course.svg",
                      CoursesPage(self.api, self.api.role))

        self.add_page("成绩管理",
                      r"student_mgmt\client\resources\icons\score.svg",
                      ScoresPage(self.api, self.api.role, self.api.user_id))

        self.add_page("统计分析",
                      r"student_mgmt\client\resources\icons\chart.svg",
                      StatsPage(self.api))

        self.add_page("大模型助手",
                      r"student_mgmt\client\resources\icons\ai.svg",
                      LLMPage(self.api, self.api.role or "student"))

        # 让菜单切换页面
        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.menu.setCurrentRow(0)

        # ============================================================
        # 加载样式表 QSS
        # ============================================================
        qss_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
        with open(qss_path, "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

    # ============================================================
    # 添加菜单项 + 对应的 Widget 页面
    # ============================================================
    def add_page(self, title, icon_path, widget):
        item = QListWidgetItem(QIcon(icon_path), title)
        self.menu.addItem(item)
        self.stack.addWidget(widget)
