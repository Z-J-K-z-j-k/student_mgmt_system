# client/pages/teachers_page.py
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QDialog,
    QFormLayout, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class TeacherEditDialog(QDialog):
    def __init__(self, parent, data=None, is_new=False):
        super().__init__(parent)
        self.is_new = is_new
        if is_new:
            self.setWindowTitle("新增教师")
        else:
            self.setWindowTitle("编辑教师信息")
        self.data = data or {}
        layout = QFormLayout(self)

        # 姓名
        self.ed_name = QLineEdit(self.data.get("name", ""))
        layout.addRow("姓名*：", self.ed_name)

        # 学院
        self.ed_department = QLineEdit(self.data.get("department", ""))
        layout.addRow("学院：", self.ed_department)

        # 职称
        self.ed_title = QLineEdit(self.data.get("title", ""))
        layout.addRow("职称：", self.ed_title)

        # 电话
        self.ed_phone = QLineEdit(self.data.get("phone", ""))
        layout.addRow("电话：", self.ed_phone)

        # 邮箱
        self.ed_email = QLineEdit(self.data.get("email", ""))
        layout.addRow("邮箱：", self.ed_email)

        # 研究方向
        self.ed_research = QLineEdit(self.data.get("research", ""))
        layout.addRow("研究方向：", self.ed_research)

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
            "name": self.ed_name.text().strip(),
            "department": self.ed_department.text().strip(),
            "title": self.ed_title.text().strip(),
            "phone": self.ed_phone.text().strip(),
            "email": self.ed_email.text().strip(),
            "research": self.ed_research.text().strip(),
        }

    def accept(self):
        # 验证必填字段
        if not self.ed_name.text().strip():
            QMessageBox.warning(self, "验证失败", "姓名不能为空")
            return
        super().accept()

class TeachersPage(QWidget):
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
        self.ed_keyword.setPlaceholderText("关键字（姓名/工号/学院）")
        self.ed_keyword.returnPressed.connect(self.refresh)
        row1.addWidget(QLabel("关键字："))
        row1.addWidget(self.ed_keyword)
        row1.addStretch()
        
        # 第二行：详细搜索条件
        row2 = QHBoxLayout()
        self.ed_teacher_id = QLineEdit()
        self.ed_teacher_id.setPlaceholderText("工号（精确）")
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("姓名（模糊）")
        self.ed_department = QLineEdit()
        self.ed_department.setPlaceholderText("学院（模糊）")
        
        row2.addWidget(QLabel("工号："))
        row2.addWidget(self.ed_teacher_id)
        row2.addWidget(QLabel("姓名："))
        row2.addWidget(self.ed_name)
        row2.addWidget(QLabel("学院："))
        row2.addWidget(self.ed_department)
        
        # 第三行：按钮
        row3 = QHBoxLayout()
        self.btn_search = QPushButton("搜索")
        self.btn_reset = QPushButton("重置")
        self.btn_search.clicked.connect(self.refresh)
        self.btn_reset.clicked.connect(self.reset_search)
        
        if role == "admin":
            self.btn_add = QPushButton("新建教师")
            self.btn_add.clicked.connect(self.add_teacher)
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
        headers = ["ID", "姓名", "学院", "职称", "电话", "邮箱", "研究方向"]
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
        self.ed_teacher_id.clear()
        self.ed_name.clear()
        self.ed_department.clear()
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
            teacher_id = self.ed_teacher_id.text().strip()
            name = self.ed_name.text().strip()
            department = self.ed_department.text().strip()
            
            if teacher_id:
                params["teacher_id"] = teacher_id
            if name:
                params["name"] = name
            if department:
                params["department"] = department
        
        try:
            resp = self.api.get("/api/teachers", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取教师列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.total = data["total"]
        self.render_table(data["data"])
        total_pages = max(1, math.ceil(self.total / self.page_size))
        self.lbl_page.setText(f"第 {self.page} / {total_pages} 页，共 {self.total} 条")

    def render_table(self, teachers):
        self.table.setRowCount(len(teachers))
        departments = set()
        
        for row_idx, t in enumerate(teachers):
            # 设置每一行的高度
            self.table.setRowHeight(row_idx, 50)
            
            # 创建单元格并设置文本颜色，确保可见
            items = [
                QTableWidgetItem(str(t.get("teacher_id", ""))),
                QTableWidgetItem(t.get("name", "")),
                QTableWidgetItem(t.get("department", "")),
                QTableWidgetItem(t.get("title", "")),
                QTableWidgetItem(t.get("phone", "")),
                QTableWidgetItem(t.get("email", "")),
                QTableWidgetItem(t.get("research", "")),
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
                
                btn_edit.clicked.connect(lambda checked, tid=t.get("teacher_id"): self.edit_teacher(tid))
                btn_delete.clicked.connect(lambda checked, tid=t.get("teacher_id"): self.delete_teacher(tid))
                
                btn_layout.addWidget(btn_edit)
                btn_layout.addWidget(btn_delete)
                btn_layout.setSpacing(8)
                btn_layout.setContentsMargins(8, 8, 8, 8)
                btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 垂直居中
                
                widget = QWidget()
                widget.setLayout(btn_layout)
                self.table.setCellWidget(row_idx, 7, widget)
            
            # 收集学院用于下拉框
            if t.get("department"):
                departments.add(t["department"])

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
        tid_item = self.table.item(row, 0)
        if not tid_item:
            return
        tid = int(tid_item.text())
        self.edit_teacher(tid)

    def edit_teacher(self, tid):
        """编辑教师"""
        if self.role != "admin":
            return
        
        # 从表格获取当前数据
        row = -1
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and int(item.text()) == tid:
                row = i
                break
        
        if row < 0:
            QMessageBox.warning(self, "错误", "未找到该教师")
            return
        
        data = {
            "teacher_id": tid,
            "name": self.table.item(row, 1).text(),
            "department": self.table.item(row, 2).text(),
            "title": self.table.item(row, 3).text(),
            "phone": self.table.item(row, 4).text(),
            "email": self.table.item(row, 5).text(),
            "research": self.table.item(row, 6).text(),
        }
        
        # 从服务器获取完整数据
        try:
            resp = self.api.get("/api/teachers", params={"teacher_id": str(tid), "page": 1, "page_size": 1})
            server_data = resp.json()
            if server_data.get("status") == "ok" and server_data.get("data") and len(server_data["data"]) > 0:
                data.update(server_data["data"][0])
        except Exception as e:
            print(f"获取教师详细信息失败: {e}")  # 如果获取失败，使用表格数据

        dlg = TeacherEditDialog(self, data, is_new=False)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                resp = self.api.put(f"/api/teachers/{tid}", json=new_data)
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "保存成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "保存失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def add_teacher(self):
        """新增教师"""
        dlg = TeacherEditDialog(self, is_new=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            try:
                resp = self.api.post("/api/teachers", json=new_data)
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

    def delete_teacher(self, tid):
        """删除教师"""
        if self.role != "admin":
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除工号为 {tid} 的教师吗？\n此操作将把该教师的所有课程设置为无教师，且无法恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            resp = self.api.delete(f"/api/teachers/{tid}")
            result = resp.json()
            if result.get("status") == "ok":
                QMessageBox.information(self, "成功", "删除成功")
                self.refresh()
            else:
                QMessageBox.warning(self, "错误", result.get("msg", "删除失败"))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败：{e}")
