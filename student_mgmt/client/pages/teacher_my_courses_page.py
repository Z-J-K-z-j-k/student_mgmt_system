# client/pages/teacher_my_courses_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHBoxLayout, QLabel
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

        title_layout = QHBoxLayout()
        title = QLabel("📘 我教授的课程")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        title_layout.addWidget(self.btn_refresh)
        layout.addLayout(title_layout)

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

        courses = data.get("data", [])
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

        if not courses:
            # 不显示消息框，避免干扰用户
            pass

