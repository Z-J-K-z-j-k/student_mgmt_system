# client/pages/scores_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QLineEdit, QPushButton, QMessageBox, QInputDialog
)
from ..utils.api_client import APIClient

class ScoresPage(QWidget):
    def __init__(self, api: APIClient, role: str, user_id: int):
        super().__init__()
        self.api = api
        self.role = role
        self.user_id = user_id

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.ed_stu_id = QLineEdit()
        self.ed_stu_id.setPlaceholderText("按学生ID过滤（可选）")
        self.btn_filter = QPushButton("过滤")
        self.btn_filter.clicked.connect(self.refresh)
        top.addWidget(self.ed_stu_id)
        top.addWidget(self.btn_filter)

        if role in ("admin", "teacher"):
            self.btn_edit = QPushButton("修改所选成绩")
            self.btn_edit.clicked.connect(self.edit_score)
            top.addWidget(self.btn_edit)

        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "学号", "姓名", "课程", "成绩", "学期"]
        )
        from PyQt6.QtWidgets import QHeaderView

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        self.refresh()

    def refresh(self):
        params = {}
        if self.ed_stu_id.text().strip():
            params["student_id"] = self.ed_stu_id.text().strip()

        try:
            resp = self.api.get("/api/scores", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取成绩失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        scores = data["data"]
        self.table.setRowCount(len(scores))
        for i, s in enumerate(scores):
            self.table.setItem(i, 0, QTableWidgetItem(str(s["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(s["student_no"]))
            self.table.setItem(i, 2, QTableWidgetItem(s["student_name"]))
            self.table.setItem(i, 3, QTableWidgetItem(s["course_name"]))
            self.table.setItem(i, 4, QTableWidgetItem(str(s["score"])))
            self.table.setItem(i, 5, QTableWidgetItem(s["term"]))

    def edit_score(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一行")
            return
        eid = int(self.table.item(row, 0).text())
        old_score = float(self.table.item(row, 4).text())
        new_score, ok = QInputDialog.getDouble(self, "修改成绩", "新成绩：", old_score, 0, 100, 1)
        if not ok:
            return

        try:
            self.api.put(f"/api/scores/{eid}", json={"score": new_score})
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修改失败：{e}")
        else:
            self.refresh()
