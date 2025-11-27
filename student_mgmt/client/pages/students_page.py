# client/pages/students_page.py
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QDialog,
    QFormLayout, QSpinBox, QDoubleSpinBox, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class StudentEditDialog(QDialog):
    def __init__(self, parent, data=None, is_new=False):
        super().__init__(parent)
        self.is_new = is_new
        if is_new:
            self.setWindowTitle("新增学生")
        else:
            self.setWindowTitle("编辑学生信息")
        self.data = data or {}
        layout = QFormLayout(self)

        # 姓名
        self.ed_name = QLineEdit(self.data.get("name", ""))
        layout.addRow("姓名*：", self.ed_name)

        # 性别（下拉框）
        self.combo_gender = QComboBox()
        self.combo_gender.addItems(["male", "female"])
        gender = self.data.get("gender", "male")
        if gender in ["male", "female"]:
            idx = self.combo_gender.findText(gender)
            if idx >= 0:
                self.combo_gender.setCurrentIndex(idx)
        layout.addRow("性别*：", self.combo_gender)

        # 年龄
        self.spin_age = QSpinBox()
        self.spin_age.setRange(0, 150)
        self.spin_age.setValue(self.data.get("age") or 0)
        self.spin_age.setSpecialValueText("未设置")
        layout.addRow("年龄：", self.spin_age)

        # 专业
        self.ed_major = QLineEdit(self.data.get("major", ""))
        layout.addRow("专业：", self.ed_major)

        # 年级
        self.spin_grade = QSpinBox()
        self.spin_grade.setRange(0, 10)
        self.spin_grade.setValue(self.data.get("grade") or 0)
        self.spin_grade.setSpecialValueText("未设置")
        layout.addRow("年级：", self.spin_grade)

        # 班级
        self.ed_class = QLineEdit(self.data.get("class_name", ""))
        layout.addRow("班级：", self.ed_class)

        # 电话
        self.ed_phone = QLineEdit(self.data.get("phone", ""))
        layout.addRow("电话：", self.ed_phone)

        # 邮箱
        self.ed_email = QLineEdit(self.data.get("email", ""))
        layout.addRow("邮箱：", self.ed_email)

        # GPA
        self.spin_gpa = QDoubleSpinBox()
        self.spin_gpa.setRange(0.0, 5.0)
        self.spin_gpa.setDecimals(2)
        self.spin_gpa.setSingleStep(0.01)
        gpa = self.data.get("gpa")
        if gpa is not None:
            self.spin_gpa.setValue(float(gpa))
        else:
            self.spin_gpa.setSpecialValueText("未设置")
        layout.addRow("GPA：", self.spin_gpa)

        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("保存")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)

        layout.addRow(btn_box)

    def get_data(self):
        age = self.spin_age.value()
        grade = self.spin_grade.value()
        gpa = self.spin_gpa.value()
        
        data = {
            "name": self.ed_name.text().strip(),
            "gender": self.combo_gender.currentText(),
            "major": self.ed_major.text().strip(),
            "class_name": self.ed_class.text().strip(),
            "phone": self.ed_phone.text().strip(),
            "email": self.ed_email.text().strip(),
        }
        
        # 只添加非默认值
        if age > 0:
            data["age"] = age
        if grade > 0:
            data["grade"] = grade
        if gpa > 0:
            data["gpa"] = gpa
        
        return data

    def accept(self):
        # 验证必填字段
        if not self.ed_name.text().strip():
            QMessageBox.warning(self, "验证失败", "姓名不能为空")
            return
        super().accept()

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
        search_layout = QVBoxLayout()
        
        # 第一行：通用搜索
        row1 = QHBoxLayout()
        self.ed_keyword = QLineEdit()
        self.ed_keyword.setPlaceholderText("关键字（姓名/学号/专业）")
        self.ed_keyword.returnPressed.connect(self.refresh)
        row1.addWidget(QLabel("关键字："))
        row1.addWidget(self.ed_keyword)
        row1.addStretch()
        
        # 第二行：详细搜索条件
        row2 = QHBoxLayout()
        self.ed_student_id = QLineEdit()
        self.ed_student_id.setPlaceholderText("学号（精确）")
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("姓名（模糊）")
        self.ed_major = QLineEdit()
        self.ed_major.setPlaceholderText("专业（模糊）")
        self.combo_class = QComboBox()
        self.combo_class.setEditable(True)
        self.combo_class.setPlaceholderText("班级（精确）")
        
        row2.addWidget(QLabel("学号："))
        row2.addWidget(self.ed_student_id)
        row2.addWidget(QLabel("姓名："))
        row2.addWidget(self.ed_name)
        row2.addWidget(QLabel("专业："))
        row2.addWidget(self.ed_major)
        row2.addWidget(QLabel("班级："))
        row2.addWidget(self.combo_class)
        
        # 第三行：按钮
        row3 = QHBoxLayout()
        self.btn_search = QPushButton("搜索")
        self.btn_reset = QPushButton("重置")
        self.btn_search.clicked.connect(self.refresh)
        self.btn_reset.clicked.connect(self.reset_search)
        
        if role == "admin":
            self.btn_add = QPushButton("新建学生")
            self.btn_add.clicked.connect(self.add_student)
            row3.addWidget(self.btn_add)
        
        row3.addStretch()
        row3.addWidget(self.btn_search)
        row3.addWidget(self.btn_reset)
        
        search_layout.addLayout(row1)
        search_layout.addLayout(row2)
        search_layout.addLayout(row3)
        main_layout.addLayout(search_layout)

        # --- 表格 ---
        self.table = QTableWidget()
        # 如果是管理员，添加操作列
        col_count = 7 if role != "admin" else 8
        self.table.setColumnCount(col_count)
        headers = ["ID", "姓名", "性别", "专业", "班级", "电话", "邮箱"]
        if role == "admin":
            headers.append("操作")
        self.table.setHorizontalHeaderLabels(headers)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 设置默认行高，让按钮有更多空间
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.verticalHeader().setMinimumSectionSize(50)

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

    def reset_search(self):
        """重置搜索条件"""
        self.ed_keyword.clear()
        self.ed_student_id.clear()
        self.ed_name.clear()
        self.ed_major.clear()
        self.combo_class.setCurrentIndex(-1)
        self.combo_class.setCurrentText("")
        self.page = 1
        self.refresh()

    def refresh(self):
        params = {
            "page": self.page,
            "page_size": self.page_size,
        }
        
        # 如果有关键字，使用通用搜索
        keyword = self.ed_keyword.text().strip()
        if keyword:
            params["keyword"] = keyword
        else:
            # 否则使用详细搜索条件
            student_id = self.ed_student_id.text().strip()
            name = self.ed_name.text().strip()
            major = self.ed_major.text().strip()
            class_name = self.combo_class.currentText().strip()
            
            if student_id:
                params["student_id"] = student_id
            if name:
                params["name"] = name
            if major:
                params["major"] = major
            if class_name:
                params["class_name"] = class_name
        
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
        majors = set()
        
        # 设置行高，让按钮有更多空间
        row_height = 50  # 增加行高到50像素
        
        for row_idx, s in enumerate(students):
            # 设置每一行的高度
            self.table.setRowHeight(row_idx, row_height)
            
            # 创建单元格并设置文本颜色，确保可见
            items = [
                QTableWidgetItem(str(s.get("student_id", ""))),
                QTableWidgetItem(s.get("name", "")),
                QTableWidgetItem(s.get("gender", "")),
                QTableWidgetItem(s.get("major", "")),
                QTableWidgetItem(s.get("class_name", "")),
                QTableWidgetItem(s.get("phone", "")),
                QTableWidgetItem(s.get("email", "")),
            ]
            # 设置所有单元格为只读，并确保文本颜色可见
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))  # 深色文本，确保可见
            
            for col_idx, item in enumerate(items):
                self.table.setItem(row_idx, col_idx, item)
            
            # 如果是管理员，添加操作按钮
            if self.role == "admin":
                btn_layout = QHBoxLayout()
                btn_edit = QPushButton("编辑")
                btn_delete = QPushButton("删除")
                
                # 设置按钮样式，确保文字清晰可见，增大字体和尺寸
                btn_edit.setStyleSheet("""
                    QPushButton {
                        background-color: #3a8dd0;
                        color: #ffffff;
                        border: none;
                        border-radius: 5px;
                        padding: 6px 16px 10px 16px;
                        font-size: 14px;
                        font-weight: bold;
                        min-width: 60px;
                        min-height: 32px;
                    }
                    QPushButton:hover {
                        background-color: #5BA0FF;
                    }
                    QPushButton:pressed {
                        background-color: #2F74D0;
                    }
                """)
                
                btn_delete.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: #ffffff;
                        border: none;
                        border-radius: 5px;
                        padding: 6px 16px 10px 16px;
                        font-size: 14px;
                        font-weight: bold;
                        min-width: 60px;
                        min-height: 32px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                    QPushButton:pressed {
                        background-color: #a93226;
                    }
                """)
                
                btn_edit.clicked.connect(lambda checked, sid=s.get("student_id"): self.edit_student(sid))
                btn_delete.clicked.connect(lambda checked, sid=s.get("student_id"): self.delete_student(sid))
                
                btn_layout.addWidget(btn_edit)
                btn_layout.addWidget(btn_delete)
                btn_layout.setSpacing(8)
                btn_layout.setContentsMargins(8, 8, 8, 8)
                btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 垂直居中
                
                widget = QWidget()
                widget.setLayout(btn_layout)
                self.table.setCellWidget(row_idx, 7, widget)
            
            # 收集班级和专业用于下拉框
            if s.get("class_name"):
                classes.add(s["class_name"])
            if s.get("major"):
                majors.add(s["major"])

        # 刷新班级和专业列表
        existing_classes = set(self.combo_class.itemText(i) for i in range(self.combo_class.count()))
        new_classes = sorted(classes - existing_classes)
        for c in new_classes:
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

    # ---------- 编辑 / 新增 / 删除 ----------

    def cell_double_clicked(self, row, column):
        """双击单元格编辑（仅管理员）"""
        if self.role != "admin":
            return
        sid_item = self.table.item(row, 0)
        if not sid_item:
            return
        sid = int(sid_item.text())
        self.edit_student(sid)

    def edit_student(self, sid):
        """编辑学生"""
        if self.role != "admin":
            return
        
        # 从表格获取当前数据
        row = -1
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and int(item.text()) == sid:
                row = i
                break
        
        if row < 0:
            QMessageBox.warning(self, "错误", "未找到该学生")
            return
        
        data = {
            "student_id": sid,
            "name": self.table.item(row, 1).text(),
            "gender": self.table.item(row, 2).text(),
            "major": self.table.item(row, 3).text(),
            "class_name": self.table.item(row, 4).text(),
            "phone": self.table.item(row, 5).text(),
            "email": self.table.item(row, 6).text(),
        }
        
        # 从服务器获取完整数据（包括age, grade, gpa等）
        try:
            resp = self.api.get("/api/students", params={"student_id": str(sid), "page": 1, "page_size": 1})
            server_data = resp.json()
            if server_data.get("status") == "ok" and server_data.get("data") and len(server_data["data"]) > 0:
                data.update(server_data["data"][0])
        except Exception as e:
            print(f"获取学生详细信息失败: {e}")  # 如果获取失败，使用表格数据

        dlg = StudentEditDialog(self, data, is_new=False)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                resp = self.api.put(f"/api/students/{sid}", json=new_data)
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "保存成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "保存失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def add_student(self):
        """新增学生"""
        dlg = StudentEditDialog(self, is_new=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                resp = self.api.post("/api/students", json=new_data)
                result = resp.json()
                if result.get("status") == "ok":
                    username = result.get("username", "")
                    password = result.get("password", "")
                    msg = f"创建成功！\n用户名：{username}\n初始密码：{password}"
                    QMessageBox.information(self, "成功", msg)
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "创建失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败：{e}")

    def delete_student(self, sid):
        """删除学生"""
        if self.role != "admin":
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除学号为 {sid} 的学生吗？\n此操作将同时删除该学生的所有成绩记录，且无法恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            resp = self.api.delete(f"/api/students/{sid}")
            result = resp.json()
            if result.get("status") == "ok":
                QMessageBox.information(self, "成功", "删除成功")
                self.refresh()
            else:
                QMessageBox.warning(self, "错误", result.get("msg", "删除失败"))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败：{e}")
