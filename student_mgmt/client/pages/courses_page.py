# client/pages/courses_page.py
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QDialog,
    QFormLayout, QSpinBox, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class CourseEditDialog(QDialog):
    def __init__(self, parent, data=None, is_new=False, teachers_list=None):
        super().__init__(parent)
        self.is_new = is_new
        if is_new:
            self.setWindowTitle("新增课程")
        else:
            self.setWindowTitle("编辑课程信息")
        self.data = data or {}
        self.teachers_list = teachers_list or []
        layout = QFormLayout(self)

        # 课程名
        self.ed_course_name = QLineEdit(self.data.get("course_name", ""))
        layout.addRow("课程名*：", self.ed_course_name)

        # 任课教师（下拉框）
        self.combo_teacher = QComboBox()
        self.combo_teacher.addItem("（无）", None)
        for teacher in self.teachers_list:
            teacher_id = teacher.get("teacher_id")
            teacher_name = teacher.get("name", "")
            if teacher_id and teacher_name:
                self.combo_teacher.addItem(f"{teacher_name} (ID: {teacher_id})", teacher_id)
        
        # 设置当前选中的教师
        current_teacher_id = self.data.get("teacher_id")
        if current_teacher_id:
            for i in range(self.combo_teacher.count()):
                if self.combo_teacher.itemData(i) == current_teacher_id:
                    self.combo_teacher.setCurrentIndex(i)
                    break
        layout.addRow("任课教师：", self.combo_teacher)

        # 学分
        self.spin_credit = QSpinBox()
        self.spin_credit.setRange(1, 10)
        credit = self.data.get("credit")
        if credit is not None:
            self.spin_credit.setValue(int(credit))
        else:
            self.spin_credit.setValue(2)  # 默认2学分
        layout.addRow("学分*：", self.spin_credit)

        # 学期
        self.ed_semester = QLineEdit(self.data.get("semester", ""))
        self.ed_semester.setPlaceholderText("例如：2024-2025-1")
        layout.addRow("学期：", self.ed_semester)

        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("保存")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)

        layout.addRow(btn_box)

    def get_data(self):
        teacher_id = self.combo_teacher.currentData()
        return {
            "course_name": self.ed_course_name.text().strip(),
            "teacher_id": teacher_id,
            "credit": self.spin_credit.value(),
            "semester": self.ed_semester.text().strip(),
        }

    def accept(self):
        # 验证必填字段
        if not self.ed_course_name.text().strip():
            QMessageBox.warning(self, "验证失败", "课程名不能为空")
            return
        super().accept()

class CoursesPage(QWidget):
    def __init__(self, api: APIClient, role: str):
        super().__init__()
        self.api = api
        self.role = role

        self.page = 1
        self.page_size = 15
        self.total = 0
        self.teachers_list = []  # 缓存教师列表

        main_layout = QVBoxLayout(self)

        # --- 顶部搜索栏 ---
        search_layout = QVBoxLayout()
        
        # 第一行：通用搜索
        row1 = QHBoxLayout()
        self.ed_keyword = QLineEdit()
        self.ed_keyword.setPlaceholderText("关键字（课程号/课程名/任课教师）")
        self.ed_keyword.returnPressed.connect(self.refresh)
        row1.addWidget(QLabel("关键字："))
        row1.addWidget(self.ed_keyword)
        row1.addStretch()
        
        # 第二行：详细搜索条件
        row2 = QHBoxLayout()
        self.ed_course_id = QLineEdit()
        self.ed_course_id.setPlaceholderText("课程号（精确）")
        self.ed_course_name = QLineEdit()
        self.ed_course_name.setPlaceholderText("课程名（模糊）")
        self.ed_teacher_name = QLineEdit()
        self.ed_teacher_name.setPlaceholderText("任课教师（模糊）")
        
        row2.addWidget(QLabel("课程号："))
        row2.addWidget(self.ed_course_id)
        row2.addWidget(QLabel("课程名："))
        row2.addWidget(self.ed_course_name)
        row2.addWidget(QLabel("任课教师："))
        row2.addWidget(self.ed_teacher_name)
        
        # 第三行：按钮
        row3 = QHBoxLayout()
        self.btn_search = QPushButton("搜索")
        self.btn_reset = QPushButton("重置")
        self.btn_search.clicked.connect(self.refresh)
        self.btn_reset.clicked.connect(self.reset_search)
        
        if role == "admin":
            self.btn_add = QPushButton("新建课程")
            self.btn_add.clicked.connect(self.add_course)
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
        col_count = 6 if role != "admin" else 7
        self.table.setColumnCount(col_count)
        headers = ["ID", "课程号", "课程名", "任课教师", "学分", "学期"]
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

        # 加载教师列表
        self.load_teachers()
        self.refresh()

    # ---------- 数据加载 ----------

    def load_teachers(self):
        """加载教师列表，用于下拉框"""
        try:
            resp = self.api.get("/api/teachers", params={"page": 1, "page_size": 1000})
            data = resp.json()
            if data.get("status") == "ok":
                self.teachers_list = data.get("data", [])
        except Exception as e:
            print(f"加载教师列表失败: {e}")
            self.teachers_list = []

    def reset_search(self):
        """重置搜索条件"""
        self.ed_keyword.clear()
        self.ed_course_id.clear()
        self.ed_course_name.clear()
        self.ed_teacher_name.clear()
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
            course_id = self.ed_course_id.text().strip()
            course_name = self.ed_course_name.text().strip()
            teacher_name = self.ed_teacher_name.text().strip()
            
            if course_id:
                params["course_id"] = course_id
            if course_name:
                params["course_name"] = course_name
            if teacher_name:
                params["teacher_name"] = teacher_name
        
        try:
            resp = self.api.get("/api/courses", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.total = data.get("total", 0)
        self.render_table(data.get("data", []))
        total_pages = max(1, math.ceil(self.total / self.page_size))
        self.lbl_page.setText(f"第 {self.page} / {total_pages} 页，共 {self.total} 条")

    def render_table(self, courses):
        self.table.setRowCount(len(courses))
        
        for row_idx, c in enumerate(courses):
            # 设置每一行的高度
            self.table.setRowHeight(row_idx, 50)
            
            # 创建单元格并设置文本颜色，确保可见
            items = [
                QTableWidgetItem(str(c.get("course_id", ""))),
                QTableWidgetItem(str(c.get("course_id", ""))),  # 课程号用course_id
                QTableWidgetItem(c.get("course_name", "")),
                QTableWidgetItem(c.get("teacher_name", "") or "（无）"),
                QTableWidgetItem(str(c.get("credit", "") or "")),
                QTableWidgetItem(c.get("semester", "") or ""),
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
                
                btn_edit.clicked.connect(lambda checked, cid=c.get("course_id"): self.edit_course(cid))
                btn_delete.clicked.connect(lambda checked, cid=c.get("course_id"): self.delete_course(cid))
                
                btn_layout.addWidget(btn_edit)
                btn_layout.addWidget(btn_delete)
                btn_layout.setSpacing(8)
                btn_layout.setContentsMargins(8, 8, 8, 8)
                btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 垂直居中
                
                widget = QWidget()
                widget.setLayout(btn_layout)
                self.table.setCellWidget(row_idx, 6, widget)

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
        cid_item = self.table.item(row, 0)
        if not cid_item:
            return
        cid = int(cid_item.text())
        self.edit_course(cid)

    def edit_course(self, cid):
        """编辑课程"""
        if self.role != "admin":
            return
        
        # 从表格获取当前数据
        row = -1
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and int(item.text()) == cid:
                row = i
                break
        
        if row < 0:
            QMessageBox.warning(self, "错误", "未找到该课程")
            return
        
        data = {
            "course_id": cid,
            "course_name": self.table.item(row, 2).text(),
            "teacher_name": self.table.item(row, 3).text(),
            "credit": self.table.item(row, 4).text(),
            "semester": self.table.item(row, 5).text(),
        }
        
        # 从服务器获取完整数据（包括teacher_id等）
        try:
            resp = self.api.get("/api/courses", params={"course_id": str(cid), "page": 1, "page_size": 1})
            server_data = resp.json()
            if server_data.get("status") == "ok" and server_data.get("data") and len(server_data["data"]) > 0:
                data.update(server_data["data"][0])
        except Exception as e:
            print(f"获取课程详细信息失败: {e}")  # 如果获取失败，使用表格数据

        dlg = CourseEditDialog(self, data, is_new=False, teachers_list=self.teachers_list)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                resp = self.api.put(f"/api/courses/{cid}", json=new_data)
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "保存成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "保存失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def add_course(self):
        """新增课程"""
        # 确保教师列表已加载
        if not self.teachers_list:
            self.load_teachers()
        
        dlg = CourseEditDialog(self, is_new=True, teachers_list=self.teachers_list)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                resp = self.api.post("/api/courses", json=new_data)
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "创建成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "创建失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败：{e}")

    def delete_course(self, cid):
        """删除课程"""
        if self.role != "admin":
            return
        
        # 获取课程名用于确认对话框
        course_name = ""
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and int(item.text()) == cid:
                course_name = self.table.item(i, 2).text()
                break
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除课程号为 {cid} 的课程「{course_name}」吗？\n此操作将同时删除该课程的所有成绩记录（Cascade删除），且无法恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            resp = self.api.delete(f"/api/courses/{cid}")
            result = resp.json()
            if result.get("status") == "ok":
                QMessageBox.information(self, "成功", "删除成功")
                self.refresh()
            else:
                QMessageBox.warning(self, "错误", result.get("msg", "删除失败"))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败：{e}")
