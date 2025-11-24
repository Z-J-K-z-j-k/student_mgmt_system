# client/pages/teachers_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QDialog, QFormLayout, QLineEdit,
    QMessageBox
)
from ..utils.api_client import APIClient

class TeacherEditDialog(QDialog):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.setWindowTitle("教师信息")
        self.data = data or {}
        layout = QFormLayout(self)

        self.ed_no = QLineEdit(self.data.get("teacher_no", ""))
        self.ed_name = QLineEdit(self.data.get("name", ""))
        self.ed_dept = QLineEdit(self.data.get("dept", ""))
        self.ed_title = QLineEdit(self.data.get("title", ""))
        self.ed_phone = QLineEdit(self.data.get("phone", ""))
        self.ed_email = QLineEdit(self.data.get("email", ""))

        layout.addRow("工号：", self.ed_no)
        layout.addRow("姓名：", self.ed_name)
        layout.addRow("学院：", self.ed_dept)
        layout.addRow("职称：", self.ed_title)
        layout.addRow("电话：", self.ed_phone)
        layout.addRow("邮箱：", self.ed_email)

        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("保存")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)
        layout.addRow(btn_box)

    def get_data(self):
        return {
            "teacher_no": self.ed_no.text().strip(),
            "name": self.ed_name.text().strip(),
            "dept": self.ed_dept.text().strip(),
            "title": self.ed_title.text().strip(),
            "phone": self.ed_phone.text().strip(),
            "email": self.ed_email.text().strip(),
        }

class TeachersPage(QWidget):
    def __init__(self, api: APIClient, role: str):
        super().__init__()
        self.api = api
        self.role = role

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "工号", "姓名", "学院", "职称", "电话/邮箱"]
        )
        from PyQt6.QtWidgets import QHeaderView

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        btn_box = QHBoxLayout()
        if role == "admin":
            self.btn_refresh = QPushButton("刷新")
            self.btn_refresh.clicked.connect(self.refresh)
            btn_box.addWidget(self.btn_refresh)
        layout.addLayout(btn_box)

        self.refresh()

    def refresh(self):
        try:
            resp = self.api.get("/api/teachers")
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取教师列表失败：{e}")
            return
        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        ts = data["data"]
        self.table.setRowCount(len(ts))
        for i, t in enumerate(ts):
            self.table.setItem(i, 0, QTableWidgetItem(str(t["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(t["teacher_no"]))
            self.table.setItem(i, 2, QTableWidgetItem(t["name"]))
            self.table.setItem(i, 3, QTableWidgetItem(t.get("dept", "")))
            self.table.setItem(i, 4, QTableWidgetItem(t.get("title", "")))
            self.table.setItem(i, 5, QTableWidgetItem(f'{t.get("phone","")} / {t.get("email","")}'))
