# client/pages/course_schedule_page.py
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QDialog,
    QFormLayout, QSpinBox, QComboBox, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class CourseScheduleEditDialog(QDialog):
    def __init__(self, parent, api, data=None, is_new=False):
        super().__init__(parent)
        self.api = api
        self.is_new = is_new
        if is_new:
            self.setWindowTitle("新增课程安排")
        else:
            self.setWindowTitle("编辑课程安排")
        self.data = data or {}
        layout = QFormLayout(self)

        # 课程ID
        self.ed_course_id = QLineEdit(str(self.data.get("course_id", "")))
        layout.addRow("课程ID*：", self.ed_course_id)

        # 教师ID
        self.ed_teacher_id = QLineEdit(str(self.data.get("teacher_id", "")))
        layout.addRow("教师ID*：", self.ed_teacher_id)

        # 学期
        self.ed_semester = QLineEdit(self.data.get("semester", ""))
        layout.addRow("学期*：", self.ed_semester)

        # 星期
        self.combo_day = QComboBox()
        self.combo_day.addItems(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        day = self.data.get("day_of_week", "Mon")
        idx = self.combo_day.findText(day)
        if idx >= 0:
            self.combo_day.setCurrentIndex(idx)
        layout.addRow("星期*：", self.combo_day)

        # 开始节次
        self.spin_period_start = QSpinBox()
        self.spin_period_start.setRange(1, 12)
        self.spin_period_start.setValue(self.data.get("period_start") or 1)
        layout.addRow("开始节次*：", self.spin_period_start)

        # 结束节次
        self.spin_period_end = QSpinBox()
        self.spin_period_end.setRange(1, 12)
        self.spin_period_end.setValue(self.data.get("period_end") or 1)
        layout.addRow("结束节次*：", self.spin_period_end)

        # 教室ID（可选）
        self.ed_classroom_id = QLineEdit()
        classroom_id = self.data.get("classroom_id")
        if classroom_id:
            self.ed_classroom_id.setText(str(classroom_id))
        self.ed_classroom_id.setPlaceholderText("可选，留空表示未分配教室")
        layout.addRow("教室ID：", self.ed_classroom_id)

        # 周次
        self.ed_weeks = QLineEdit(self.data.get("weeks", ""))
        self.ed_weeks.setPlaceholderText("例如: 1-16, 9-16")
        layout.addRow("周次*：", self.ed_weeks)

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
            "course_id": int(self.ed_course_id.text().strip()),
            "teacher_id": int(self.ed_teacher_id.text().strip()),
            "semester": self.ed_semester.text().strip(),
            "day_of_week": self.combo_day.currentText(),
            "period_start": self.spin_period_start.value(),
            "period_end": self.spin_period_end.value(),
            "weeks": self.ed_weeks.text().strip(),
        }
        classroom_id = self.ed_classroom_id.text().strip()
        if classroom_id:
            data["classroom_id"] = int(classroom_id)
        else:
            data["classroom_id"] = None
        return data

    def accept(self):
        # 验证必填字段
        if not self.ed_course_id.text().strip():
            QMessageBox.warning(self, "验证失败", "课程ID不能为空")
            return
        if not self.ed_teacher_id.text().strip():
            QMessageBox.warning(self, "验证失败", "教师ID不能为空")
            return
        if not self.ed_semester.text().strip():
            QMessageBox.warning(self, "验证失败", "学期不能为空")
            return
        if not self.ed_weeks.text().strip():
            QMessageBox.warning(self, "验证失败", "周次不能为空")
            return
        try:
            course_id = int(self.ed_course_id.text().strip())
            teacher_id = int(self.ed_teacher_id.text().strip())
        except ValueError:
            QMessageBox.warning(self, "验证失败", "课程ID和教师ID必须是数字")
            return
        if self.spin_period_end.value() < self.spin_period_start.value():
            QMessageBox.warning(self, "验证失败", "结束节次不能小于开始节次")
            return
        super().accept()

class CourseSchedulePage(QWidget):
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
        self.ed_keyword.setPlaceholderText("关键字（课程名/教师名）")
        self.ed_keyword.returnPressed.connect(self.refresh)
        row1.addWidget(QLabel("关键字："))
        row1.addWidget(self.ed_keyword)
        row1.addStretch()
        
        # 第二行：详细搜索条件
        row2 = QHBoxLayout()
        self.ed_schedule_id = QLineEdit()
        self.ed_schedule_id.setPlaceholderText("安排ID（精确）")
        self.ed_course_id = QLineEdit()
        self.ed_course_id.setPlaceholderText("课程ID（精确）")
        self.ed_teacher_id = QLineEdit()
        self.ed_teacher_id.setPlaceholderText("教师ID（精确）")
        self.ed_semester = QLineEdit()
        self.ed_semester.setPlaceholderText("学期（精确）")
        
        row2.addWidget(QLabel("安排ID："))
        row2.addWidget(self.ed_schedule_id)
        row2.addWidget(QLabel("课程ID："))
        row2.addWidget(self.ed_course_id)
        row2.addWidget(QLabel("教师ID："))
        row2.addWidget(self.ed_teacher_id)
        row2.addWidget(QLabel("学期："))
        row2.addWidget(self.ed_semester)
        
        # 第三行：星期筛选和按钮
        row3 = QHBoxLayout()
        self.combo_day = QComboBox()
        self.combo_day.addItem("全部")
        self.combo_day.addItems(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        row3.addWidget(QLabel("星期："))
        row3.addWidget(self.combo_day)
        
        self.btn_add = QPushButton("新建安排")
        self.btn_add.clicked.connect(self.add_schedule)
        self.btn_search = QPushButton("搜索")
        self.btn_reset = QPushButton("重置")
        self.btn_search.clicked.connect(self.refresh)
        self.btn_reset.clicked.connect(self.reset_search)
        
        row3.addStretch()
        row3.addWidget(self.btn_add)
        row3.addWidget(self.btn_search)
        row3.addWidget(self.btn_reset)
        
        search_layout.addLayout(row1)
        search_layout.addLayout(row2)
        search_layout.addLayout(row3)
        main_layout.addLayout(search_layout)

        # --- 表格 ---
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        headers = ["安排ID", "课程ID", "课程名", "教师ID", "教师名", "学期", "星期", "节次", "教室", "周次", "操作"]
        self.table.setHorizontalHeaderLabels(headers)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 设置默认行高
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
        self.ed_schedule_id.clear()
        self.ed_course_id.clear()
        self.ed_teacher_id.clear()
        self.ed_semester.clear()
        self.combo_day.setCurrentIndex(0)
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
            schedule_id = self.ed_schedule_id.text().strip()
            course_id = self.ed_course_id.text().strip()
            teacher_id = self.ed_teacher_id.text().strip()
            semester = self.ed_semester.text().strip()
            day_of_week = self.combo_day.currentText()
            
            if schedule_id:
                params["schedule_id"] = schedule_id
            if course_id:
                params["course_id"] = course_id
            if teacher_id:
                params["teacher_id"] = teacher_id
            if semester:
                params["semester"] = semester
            if day_of_week and day_of_week != "全部":
                params["day_of_week"] = day_of_week
        
        try:
            resp = self.api.get("/api/course-schedules", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程安排列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.total = data["total"]
        self.render_table(data["data"])
        total_pages = max(1, math.ceil(self.total / self.page_size))
        self.lbl_page.setText(f"第 {self.page} / {total_pages} 页，共 {self.total} 条")

    def render_table(self, schedules):
        self.table.setRowCount(len(schedules))
        
        row_height = 50
        
        for row_idx, s in enumerate(schedules):
            self.table.setRowHeight(row_idx, row_height)
            
            # 星期中文映射
            day_map = {
                "Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四",
                "Fri": "周五", "Sat": "周六", "Sun": "周日"
            }
            day_cn = day_map.get(s.get("day_of_week", ""), s.get("day_of_week", ""))
            
            # 节次显示
            period_str = f"{s.get('period_start', '')}-{s.get('period_end', '')}节"
            
            # 教室显示
            classroom_name = s.get("classroom_name", "")
            if not classroom_name:
                classroom_name = "未分配"
            
            items = [
                QTableWidgetItem(str(s.get("schedule_id", ""))),
                QTableWidgetItem(str(s.get("course_id", ""))),
                QTableWidgetItem(s.get("course_name", "")),
                QTableWidgetItem(str(s.get("teacher_id", ""))),
                QTableWidgetItem(s.get("teacher_name", "")),
                QTableWidgetItem(s.get("semester", "")),
                QTableWidgetItem(day_cn),
                QTableWidgetItem(period_str),
                QTableWidgetItem(classroom_name),
                QTableWidgetItem(s.get("weeks", "")),
            ]
            
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))
            
            for col_idx, item in enumerate(items):
                self.table.setItem(row_idx, col_idx, item)
            
            # 添加操作按钮
            btn_layout = QHBoxLayout()
            btn_edit = QPushButton("编辑")
            btn_delete = QPushButton("删除")
            
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
            
            btn_edit.clicked.connect(lambda checked, sid=s.get("schedule_id"): self.edit_schedule(sid))
            btn_delete.clicked.connect(lambda checked, sid=s.get("schedule_id"): self.delete_schedule(sid))
            
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_delete)
            btn_layout.setSpacing(8)
            btn_layout.setContentsMargins(8, 8, 8, 8)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            widget = QWidget()
            widget.setLayout(btn_layout)
            self.table.setCellWidget(row_idx, 10, widget)

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
        sid_item = self.table.item(row, 0)
        if not sid_item:
            return
        try:
            sid = int(sid_item.text())
            self.edit_schedule(sid)
        except ValueError:
            pass

    def add_schedule(self):
        """新增课程安排"""
        dialog = CourseScheduleEditDialog(self, self.api, is_new=True)
        if dialog.exec():
            data = dialog.get_data()
            try:
                resp = self.api.post("/api/course-schedules", json=data)
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "课程安排创建成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "创建失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败：{e}")

    def edit_schedule(self, sid):
        """编辑课程安排"""
        try:
            resp = self.api.get("/api/course-schedules", params={"schedule_id": str(sid), "page_size": 1})
            data = resp.json()
            if data.get("status") != "ok" or not data.get("data"):
                QMessageBox.warning(self, "错误", "课程安排不存在")
                return
            
            schedule_data = data["data"][0]
            dialog = CourseScheduleEditDialog(self, self.api, data=schedule_data, is_new=False)
            if dialog.exec():
                new_data = dialog.get_data()
                try:
                    resp = self.api.put(f"/api/course-schedules/{sid}", json=new_data)
                    result = resp.json()
                    if result.get("status") == "ok":
                        QMessageBox.information(self, "成功", "课程安排更新成功")
                        self.refresh()
                    else:
                        QMessageBox.warning(self, "错误", result.get("msg", "更新失败"))
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"更新失败：{e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程安排信息失败：{e}")

    def delete_schedule(self, sid):
        """删除课程安排"""
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除课程安排ID {sid} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                resp = self.api.delete(f"/api/course-schedules/{sid}")
                result = resp.json()
                if result.get("status") == "ok":
                    QMessageBox.information(self, "成功", "课程安排删除成功")
                    self.refresh()
                else:
                    QMessageBox.warning(self, "错误", result.get("msg", "删除失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败：{e}")

