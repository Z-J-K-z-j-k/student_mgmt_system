# client/pages/courses_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox
)
from ..utils.api_client import APIClient

class CoursesPage(QWidget):
    def __init__(self, api: APIClient, role: str):
        super().__init__()
        self.api = api
        self.role = role

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "课程号", "课程名", "任课教师", "学分", "学期"]
        )
        from PyQt6.QtWidgets import QHeaderView

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        self.refresh()

    def refresh(self):
        try:
            resp = self.api.get("/api/courses")
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程失败：{e}")
            return
        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        cs = data["data"]
        self.table.setRowCount(len(cs))
        for i, c in enumerate(cs):
            self.table.setItem(i, 0, QTableWidgetItem(str(c["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(c["course_no"]))
            self.table.setItem(i, 2, QTableWidgetItem(c["name"]))
            self.table.setItem(i, 3, QTableWidgetItem(c.get("teacher_name", "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(c.get("credit", ""))))
            self.table.setItem(i, 5, QTableWidgetItem(c.get("term", "")))
