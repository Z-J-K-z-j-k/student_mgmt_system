# client/pages/classrooms_page.py
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QDialog,
    QFormLayout, QSpinBox, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class ClassroomEditDialog(QDialog):
    def __init__(self, parent, data=None, is_new=False):
        super().__init__(parent)
        self.is_new = is_new
        if is_new:
            self.setWindowTitle("新增教室")
        else:
            self.setWindowTitle("编辑教室信息")
        self.data = data or {}
        layout = QFormLayout(self)

        # 楼栋
        self.ed_building = QLineEdit(self.data.get("building", ""))
        layout.addRow("楼栋*：", self.ed_building)

        # 房间号
        self.ed_room = QLineEdit(self.data.get("room", ""))
        layout.addRow("房间号*：", self.ed_room)

        # 容量
        self.spin_capacity = QSpinBox()
        self.spin_capacity.setRange(1, 1000)
        capacity = self.data.get("capacity")
        if capacity is not None:
            self.spin_capacity.setValue(int(capacity))
        else:
            self.spin_capacity.setValue(60)  # 默认容量
        layout.addRow("容量*：", self.spin_capacity)

        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("保存")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)

        layout.addRow(btn_box)

    def get_data(self):
        data = {
            "building": self.ed_building.text().strip(),
            "room": self.ed_room.text().strip(),
            "capacity": self.spin_capacity.value()
        }
        return data

    def accept(self):
        # 验证必填字段
        if not self.ed_building.text().strip():
            QMessageBox.warning(self, "验证失败", "楼栋不能为空")
            return
        if not self.ed_room.text().strip():
            QMessageBox.warning(self, "验证失败", "房间号不能为空")
            return
        super().accept()

class ClassroomsPage(QWidget):
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api

        self.page = 1
        self.page_size = 15
        self.total = 0

        main_layout = QVBoxLayout(self)

        # --- 顶部搜索栏 ---
        search_layout = QVBoxLayout()
        
        # 第一行：通用搜索
        row1 = QHBoxLayout()
        self.ed_keyword = QLineEdit()
        self.ed_keyword.setPlaceholderText("关键字（教室ID/楼栋/房间号）")
        self.ed_keyword.returnPressed.connect(self.refresh)
        row1.addWidget(QLabel("关键字："))
        row1.addWidget(self.ed_keyword)
        row1.addStretch()
        
        # 第二行：详细搜索条件
        row2 = QHBoxLayout()
        self.ed_classroom_id = QLineEdit()
        self.ed_classroom_id.setPlaceholderText("教室ID（精确）")
        self.ed_building = QLineEdit()
        self.ed_building.setPlaceholderText("楼栋（模糊）")
        self.ed_room = QLineEdit()
        self.ed_room.setPlaceholderText("房间号（模糊）")
        
        row2.addWidget(QLabel("教室ID："))
        row2.addWidget(self.ed_classroom_id)
        row2.addWidget(QLabel("楼栋："))
        row2.addWidget(self.ed_building)
        row2.addWidget(QLabel("房间号："))
        row2.addWidget(self.ed_room)
        
        # 第三行：按钮
        row3 = QHBoxLayout()
        self.btn_add = QPushButton("新建教室")
        self.btn_add.clicked.connect(self.add_classroom)
        self.btn_search = QPushButton("搜索")
        self.btn_reset = QPushButton("重置")
        self.btn_search.clicked.connect(self.refresh)
        self.btn_reset.clicked.connect(self.reset_search)
        
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
        self.table.setColumnCount(5)
        headers = ["教室ID", "楼栋", "房间号", "容量", "操作"]
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
        self.ed_classroom_id.clear()
        self.ed_building.clear()
        self.ed_room.clear()
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
            classroom_id = self.ed_classroom_id.text().strip()
            building = self.ed_building.text().strip()
            room = self.ed_room.text().strip()
            
            if classroom_id:
                params["classroom_id"] = classroom_id
            if building:
                params["building"] = building
            if room:
                params["room"] = room
        
        try:
            resp = self.api.get("/api/classrooms", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取教室列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.total = data["total"]
        self.render_table(data["data"])
        total_pages = max(1, math.ceil(self.total / self.page_size))
        self.lbl_page.setText(f"第 {self.page} / {total_pages} 页，共 {self.total} 条")

    def render_table(self, classrooms):
        self.table.setRowCount(len(classrooms))
        
        # 设置行高，让按钮有更多空间
        row_height = 50
        
        for row_idx, c in enumerate(classrooms):
            # 设置每一行的高度
            self.table.setRowHeight(row_idx, row_height)
            
            # 创建单元格并设置文本颜色，确保可见
            items = [
                QTableWidgetItem(str(c.get("classroom_id", ""))),
                QTableWidgetItem(c.get("building", "")),
                QTableWidgetItem(c.get("room", "")),
                QTableWidgetItem(str(c.get("capacity", ""))),
            ]
            # 设置所有单元格为只读，并确保文本颜色可见
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))
            
            for col_idx, item in enumerate(items):
                self.table.setItem(row_idx, col_idx, item)
            
            # 添加操作按钮
            btn_layout = QHBoxLayout()
            btn_edit = QPushButton("编辑")
            btn_delete = QPushButton("删除")
            
            # 设置按钮样式
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
            
            btn_edit.clicked.connect(lambda checked, cid=c.get("classroom_id"): self.edit_classroom(cid))
            btn_delete.clicked.connect(lambda checked, cid=c.get("classroom_id"): self.delete_classroom(cid))
            
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_delete)
            btn_layout.setSpacing(8)
            btn_layout.setContentsMargins(8, 8, 8, 8)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            widget = QWidget()
            widget.setLayout(btn_layout)
            self.table.setCellWidget(row_idx, 4, widget)

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
        """双击单元格编辑"""
        cid_item = self.table.item(row, 0)
        if not cid_item:
            return
        try:
            cid = int(cid_item.text())
            self.edit_classroom(cid)
        except ValueError:
            pass

    def add_classroom(self):
        """新增教室"""
        dialog = ClassroomEditDialog(self, is_new=True)
        if dialog.exec():
            data = dialog.get_data()
            try:
                resp = self.api.post("/api/classrooms", json=data)
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "教室创建成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "创建失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败：{e}")

    def edit_classroom(self, cid):
        """编辑教室"""
        try:
            resp = self.api.get("/api/classrooms", params={"classroom_id": str(cid), "page_size": 1})
            data = resp.json()
            if data.get("status") != "ok" or not data.get("data"):
                QMessageBox.warning(self, "错误", "教室不存在")
                return
            
            classroom_data = data["data"][0]
            dialog = ClassroomEditDialog(self, data=classroom_data, is_new=False)
            if dialog.exec():
                new_data = dialog.get_data()
                try:
                    resp = self.api.put(f"/api/classrooms/{cid}", json=new_data)
                    result = resp.json()
                    if result.get("status") == "ok":
                        QMessageBox.information(self, "成功", "教室信息更新成功")
                        self.refresh()
                    else:
                        QMessageBox.warning(self, "错误", result.get("msg", "更新失败"))
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"更新失败：{e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取教室信息失败：{e}")

    def delete_classroom(self, cid):
        """删除教室"""
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除教室ID {cid} 吗？\n如果该教室正在被课程使用，将无法删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                resp = self.api.delete(f"/api/classrooms/{cid}")
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "教室删除成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "删除失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败：{e}")

