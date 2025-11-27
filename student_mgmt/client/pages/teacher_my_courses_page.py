# client/pages/teacher_my_courses_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHBoxLayout, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class TeacherMyCoursesPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id

        layout = QVBoxLayout(self)
        self.current_courses = []

        title_layout = QHBoxLayout()
        title = QLabel("📘 我教授的课程")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        title_layout.addWidget(self.btn_refresh)
        layout.addLayout(title_layout)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("检索："))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入课程号/课程名/学期关键字")
        self.search_input.textChanged.connect(self.apply_search_filter)
        search_layout.addWidget(self.search_input)

        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.apply_search_filter)
        search_layout.addWidget(self.btn_search)

        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self.clear_search)
        search_layout.addWidget(self.btn_clear)

        search_layout.addStretch()
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "课程号", "课程名", "学分", "学期", "选课人数"]
        )
        from PyQt6.QtWidgets import QHeaderView

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        self.refresh()

    def refresh(self):
        """刷新课程列表"""
        try:
            resp = self.api.get("/api/teacher/my-courses")
            if resp.status_code != 200:
                QMessageBox.critical(self, "错误", f"服务器返回错误：{resp.status_code}")
                return
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.current_courses = data.get("data", [])
        self.apply_search_filter()

    def clear_search(self):
        """清空检索条件"""
        self.search_input.clear()
        self.apply_search_filter()

    def apply_search_filter(self):
        """根据关键字过滤课程"""
        if not hasattr(self, "current_courses"):
            return

        keyword = self.search_input.text().strip().lower()
        if not keyword:
            filtered = self.current_courses
        else:
            def match(course):
                targets = [
                    str(course.get("course_id", "")),
                    course.get("course_name", ""),
                    str(course.get("semester", "")),
                ]
                return any(keyword in (t or "").lower() for t in targets)

            filtered = [course for course in self.current_courses if match(course)]

        self.populate_table(filtered)

    def populate_table(self, courses):
        """渲染课程表格"""
        self.table.setRowCount(len(courses))

        for i, course in enumerate(courses):
            items = [
                QTableWidgetItem(str(course.get("course_id", ""))),
                QTableWidgetItem(str(course.get("course_id", ""))),  # 课程号使用course_id
                QTableWidgetItem(course.get("course_name", "")),
                QTableWidgetItem(str(course.get("credit", "") or "")),
                QTableWidgetItem(course.get("semester", "") or "N/A"),
                QTableWidgetItem(str(course.get("selected_count", 0))),
            ]
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))

            for col_idx, item in enumerate(items):
                self.table.setItem(i, col_idx, item)

