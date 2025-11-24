# client/pages/students_page.py
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QDialog,
    QFormLayout
)
from ..utils.api_client import APIClient

class StudentEditDialog(QDialog):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.setWindowTitle("学生信息")
        self.data = data or {}
        layout = QFormLayout(self)

        self.ed_sno = QLineEdit(self.data.get("student_no", ""))
        self.ed_name = QLineEdit(self.data.get("name", ""))
        self.ed_gender = QLineEdit(self.data.get("gender", ""))
        self.ed_major = QLineEdit(self.data.get("major", ""))
        self.ed_class = QLineEdit(self.data.get("class_name", ""))
        self.ed_phone = QLineEdit(self.data.get("phone", ""))
        self.ed_email = QLineEdit(self.data.get("email", ""))

        layout.addRow("学号：", self.ed_sno)
        layout.addRow("姓名：", self.ed_name)
        layout.addRow("性别：", self.ed_gender)
        layout.addRow("专业：", self.ed_major)
        layout.addRow("班级：", self.ed_class)
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
            "student_no": self.ed_sno.text().strip(),
            "name": self.ed_name.text().strip(),
            "gender": self.ed_gender.text().strip(),
            "major": self.ed_major.text().strip(),
            "class_name": self.ed_class.text().strip(),
            "phone": self.ed_phone.text().strip(),
            "email": self.ed_email.text().strip(),
        }

class StudentsPage(QWidget):
    def __init__(self, api: APIClient, role: str):
        super().__init__()
        self.api = api
        self.role = role

        self.page = 1
        self.page_size = 15
        self.total = 0

        main_layout = QVBoxLayout(self)

        # --- 顶部搜索栏 ---
        top = QHBoxLayout()
        self.ed_keyword = QLineEdit()
        self.ed_keyword.setPlaceholderText("搜索学生姓名或学号")
        self.combo_class = QComboBox()
        self.combo_class.setEditable(True)
        self.combo_class.setPlaceholderText("班级（可选）")
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.refresh)

        top.addWidget(QLabel("关键字："))
        top.addWidget(self.ed_keyword)
        top.addWidget(QLabel("班级："))
        top.addWidget(self.combo_class)
        top.addWidget(self.btn_search)

        if role == "admin":
            self.btn_add = QPushButton("新建学生")
            self.btn_add.clicked.connect(self.add_student)
            top.addWidget(self.btn_add)

        main_layout.addLayout(top)

        # --- 表格 ---
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "学号", "姓名", "性别", "专业", "班级", "电话", "邮箱"]
        )
        from PyQt6.QtWidgets import QHeaderView

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.table.cellDoubleClicked.connect(self.cell_double_clicked)
    
        main_layout.addWidget(self.table)

        # --- 分页 ---
        bottom = QHBoxLayout()
        self.lbl_page = QLabel()
        self.btn_prev = QPushButton("上一页")
        self.btn_next = QPushButton("下一页")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)
        bottom.addWidget(self.lbl_page)
        bottom.addStretch()
        bottom.addWidget(self.btn_prev)
        bottom.addWidget(self.btn_next)
        main_layout.addLayout(bottom)

        self.refresh()

    # ---------- 数据加载 ----------

    def refresh(self):
        params = {
            "page": self.page,
            "page_size": self.page_size,
            "keyword": self.ed_keyword.text().strip() or "",
            "class_name": self.combo_class.currentText().strip() or "",
        }
        try:
            resp = self.api.get("/api/students", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取学生列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.total = data["total"]
        self.render_table(data["data"])
        total_pages = max(1, math.ceil(self.total / self.page_size))
        self.lbl_page.setText(f"第 {self.page} / {total_pages} 页，共 {self.total} 条")

    def render_table(self, students):
        self.table.setRowCount(len(students))
        classes = set()
        for row_idx, s in enumerate(students):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(s["id"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(s.get("student_no", "")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(s.get("name", "")))
            self.table.setItem(row_idx, 3, QTableWidgetItem(s.get("gender", "")))
            self.table.setItem(row_idx, 4, QTableWidgetItem(s.get("major", "")))
            self.table.setItem(row_idx, 5, QTableWidgetItem(s.get("class_name", "")))
            self.table.setItem(row_idx, 6, QTableWidgetItem(s.get("phone", "")))
            self.table.setItem(row_idx, 7, QTableWidgetItem(s.get("email", "")))
            if s.get("class_name"):
                classes.add(s["class_name"])

        # 刷新班级列表
        existing = set(self.combo_class.itemText(i) for i in range(self.combo_class.count()))
        new = sorted(classes - existing)
        for c in new:
            self.combo_class.addItem(c)

    # ---------- 分页 ----------

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.refresh()

    def next_page(self):
        total_pages = max(1, math.ceil(self.total / self.page_size))
        if self.page < total_pages:
            self.page += 1
            self.refresh()

    # ---------- 编辑 / 新增 ----------

    def cell_double_clicked(self, row, column):
        if self.role != "admin":
            return
        sid_item = self.table.item(row, 0)
        if not sid_item:
            return
        sid = int(sid_item.text())

        # 取当前行数据
        data = {
            "id": sid,
            "student_no": self.table.item(row, 1).text(),
            "name": self.table.item(row, 2).text(),
            "gender": self.table.item(row, 3).text(),
            "major": self.table.item(row, 4).text(),
            "class_name": self.table.item(row, 5).text(),
            "phone": self.table.item(row, 6).text(),
            "email": self.table.item(row, 7).text(),
        }

        dlg = StudentEditDialog(self, data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                self.api.put(f"/api/students/{sid}", json=new_data)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败：{e}")
            else:
                self.refresh()

    def add_student(self):
        dlg = StudentEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                self.api.post("/api/students", json=new_data)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"新建失败：{e}")
            else:
                self.refresh()
