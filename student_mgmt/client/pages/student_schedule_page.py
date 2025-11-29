# client/pages/student_schedule_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QMessageBox, QPushButton, QComboBox, QHeaderView,
    QTabWidget, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from ..utils.api_client import APIClient


class StudentSchedulePage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.student_id = None
        self.schedule_data = []  # 存储课程表数据

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 标题和筛选区域
        title_layout = QHBoxLayout()
        title = QLabel("📅 我的课程表")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 统计信息标签
        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("""
            QLabel {
                background-color: #f0f7ff;
                border: 1px solid #b3d9ff;
                border-radius: 6px;
                padding: 8px 12px;
                color: #1f1f1f;
                font-size: 13px;
            }
        """)
        title_layout.addWidget(self.lbl_stats)

        # 学期筛选
        title_layout.addWidget(QLabel("学期："))
        self.combo_semester = QComboBox()
        self.combo_semester.addItem("请选择学期")  # 初始提示
        # 使用信号阻塞避免初始化时触发刷新
        self.combo_semester.currentTextChanged.connect(self.on_semester_changed)
        title_layout.addWidget(self.combo_semester)

        # 刷新按钮
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        title_layout.addWidget(self.btn_refresh)
        layout.addLayout(title_layout)

        # 使用TabWidget，包含周课表和课程列表两个视图
        self.tab_widget = QTabWidget()
        
        # Tab 1: 周课表视图
        schedule_tab = QWidget()
        schedule_layout = QVBoxLayout(schedule_tab)
        schedule_layout.setContentsMargins(0, 0, 0, 0)
        
        # 课程表表格（周课表形式）
        # 表格：行表示节次，列表示星期
        self.table = QTableWidget()
        self.table.setRowCount(12)  # 假设最多12节课
        self.table.setColumnCount(8)  # 星期一到星期日 + 节次列
        
        # 设置表头
        headers = ["节次", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        self.table.setHorizontalHeaderLabels(headers)
        
        # 设置行标题（节次）
        # 定义时间段（可以根据实际情况调整）
        time_slots = [
            "08:00-08:45", "08:55-09:40", "10:00-10:45", "10:55-11:40",
            "14:00-14:45", "14:55-15:40", "16:00-16:45", "16:55-17:40",
            "19:00-19:45", "19:55-20:40", "20:50-21:35", "21:45-22:30"
        ]
        for i in range(12):
            period_label = f"第{i+1}节"
            if i < len(time_slots):
                period_label += f"\n{time_slots[i]}"
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(period_label))
        
        # 设置表格样式
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
            }
            QTableWidget::item {
                padding: 8px;
                border: 1px solid #e0e0e0;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
            }
            QTableWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        
        # 设置节次列不可编辑且固定宽度
        self.table.setColumnWidth(0, 120)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        
        schedule_layout.addWidget(self.table)
        self.tab_widget.addTab(schedule_tab, "📅 周课表")
        
        # Tab 2: 课程列表视图（显示所有已选课程，包括没有课程表信息的）
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        # 提示标签
        list_info_label = QLabel("以下显示所有已选课程，包括未安排具体时间的课程：")
        list_info_label.setStyleSheet("color: #666; padding: 5px;")
        list_layout.addWidget(list_info_label)
        
        # 课程列表表格
        self.course_list_table = QTableWidget()
        self.course_list_table.setColumnCount(6)
        self.course_list_table.setHorizontalHeaderLabels(
            ["课程ID", "课程名", "学分", "学期", "教师", "课程表状态"]
        )
        self.course_list_table.horizontalHeader().setStretchLastSection(True)
        self.course_list_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.course_list_table.setAlternatingRowColors(True)
        self.course_list_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
            }
            QTableWidget::item {
                padding: 8px;
            }
        """)
        list_layout.addWidget(self.course_list_table)
        self.tab_widget.addTab(list_tab, "📋 课程列表")
        
        layout.addWidget(self.tab_widget)

        # 初始化
        self.init_student_info()
        self.init_semesters()  # 先初始化学期下拉框
        # 初始状态显示提示信息，不自动加载数据
        self.show_initial_prompt()

    def init_student_info(self):
        """初始化学生信息，获取 student_id"""
        try:
            resp = self.api.get("/api/students", params={"page": 1, "page_size": 1000})
            data = resp.json()
            if data.get("status") == "ok":
                students = data.get("data", [])
                for s in students:
                    if s.get("student_id") == self.user_id or s.get("user_id") == self.user_id:
                        self.student_id = s.get("student_id")
                        break
        except Exception as e:
            print(f"获取学生信息失败：{e}")

    def init_semesters(self):
        """初始化学期下拉框，获取所有学期"""
        if not self.student_id:
            return
        
        try:
            # 获取所有学期的数据（不传学期参数）
            params = {"student_id": str(self.student_id)}
            resp = self.api.get("/api/student/schedule", params=params)
            data = resp.json()
            
            if data.get("status") == "ok":
                all_data = data.get("data", [])
                # 提取所有学期
                semesters = set()
                for item in all_data:
                    sem = item.get("semester", "").strip()
                    if sem:
                        semesters.add(sem)
                
                # 更新学期下拉框（阻塞信号避免触发刷新）
                self.combo_semester.blockSignals(True)
                self.combo_semester.clear()
                self.combo_semester.addItem("请选择学期")  # 初始提示
                self.combo_semester.addItem("全部学期")  # 全部学期选项
                for sem in sorted(semesters):
                    self.combo_semester.addItem(sem)
                self.combo_semester.blockSignals(False)
        except Exception as e:
            print(f"获取学期列表失败：{e}")

    def on_semester_changed(self, text):
        """学期选择改变时的回调"""
        # 如果选择的是"请选择学期"，不加载数据
        if text == "请选择学期":
            self.show_initial_prompt()
            return
        # 当学期改变时，刷新显示
        self.refresh()

    def show_initial_prompt(self):
        """显示初始提示信息"""
        # 清空表格
        for row in range(12):
            for col in range(1, 8):  # 跳过节次列
                self.table.setItem(row, col, None)
        
        # 清空课程列表
        self.course_list_table.setRowCount(0)
        
        # 显示提示信息
        prompt_item = QTableWidgetItem("请在上方选择学期查看课程表")
        prompt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt_item.setForeground(QColor("#666"))
        font = QFont()
        font.setPointSize(14)
        prompt_item.setFont(font)
        self.table.setItem(5, 3, prompt_item)  # 显示在表格中间位置
        
        # 更新统计信息
        self.lbl_stats.setText("请选择学期查看课程表")
        self.schedule_data = []

    def refresh(self):
        """刷新课程表"""
        if not self.student_id:
            self.init_student_info()
        
        if not self.student_id:
            QMessageBox.warning(self, "错误", "无法获取学生ID")
            return

        try:
            params = {"student_id": str(self.student_id)}
            # 获取当前选择的学期
            semester = self.combo_semester.currentText().strip() if hasattr(self, "combo_semester") else ""
            # 如果选择了"全部学期"，不传学期参数；否则传递学期参数
            if semester and semester != "全部学期" and semester != "请选择学期":
                params["semester"] = semester
            
            resp = self.api.get("/api/student/schedule", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.schedule_data = data.get("data", [])
        
        # 清空表格
        for row in range(12):
            for col in range(1, 8):  # 跳过节次列
                self.table.setItem(row, col, None)
        
        # 填充课程表
        self.fill_schedule_table()
        
        # 填充课程列表
        self.fill_course_list()
        
        # 更新统计信息
        self.update_stats()
        
        # 如果没有数据，在第一个单元格显示提示
        if not self.schedule_data:
            empty_item = QTableWidgetItem("该学期暂无课程表数据\n请先选课")
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_item.setForeground(QColor("#999"))
            font = QFont()
            font.setPointSize(12)
            empty_item.setFont(font)
            self.table.setItem(0, 1, empty_item)

    def fill_schedule_table(self):
        """填充课程表数据到表格"""
        # 星期映射：Mon->1, Tue->2, ..., Sun->7
        day_map = {
            "Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4,
            "Fri": 5, "Sat": 6, "Sun": 7
        }
        
        # 按课程分组，处理同一课程多个时间段的情况
        courses_dict = {}
        for item in self.schedule_data:
            course_id = item.get("course_id")
            if not course_id:
                continue
            
            if course_id not in courses_dict:
                courses_dict[course_id] = {
                    "course_name": item.get("course_name", ""),
                    "credit": item.get("credit", ""),
                    "schedules": []
                }
            
            # 如果有课程表信息，添加到schedules
            if item.get("schedule_id") and item.get("day_of_week"):
                courses_dict[course_id]["schedules"].append({
                    "day_of_week": item.get("day_of_week"),
                    "period_start": item.get("period_start"),
                    "period_end": item.get("period_end"),
                    "weeks": item.get("weeks", ""),
                    "classroom": item.get("classroom", ""),
                    "teacher_name": item.get("teacher_name", "")
                })
        
        # 填充表格
        colors = [
            QColor(255, 235, 238),  # 浅红
            QColor(232, 245, 233),  # 浅绿
            QColor(227, 242, 253),  # 浅蓝
            QColor(255, 243, 224),  # 浅橙
            QColor(243, 229, 245),  # 浅紫
            QColor(255, 224, 178),  # 浅棕
            QColor(225, 245, 254),  # 浅青
        ]
        color_index = 0
        
        for course_id, course_info in courses_dict.items():
            course_name = course_info["course_name"]
            credit = course_info.get("credit", "")
            schedules = course_info["schedules"]
            
            # 如果没有课程表信息，跳过
            if not schedules:
                continue
            
            # 为每个课程分配一个颜色
            bg_color = colors[color_index % len(colors)]
            color_index += 1
            
            # 处理该课程的每个时间段
            for schedule in schedules:
                day_of_week = schedule["day_of_week"]
                period_start = schedule.get("period_start", 1)
                period_end = schedule.get("period_end", period_start)
                weeks = schedule.get("weeks", "")
                classroom = schedule.get("classroom", "")
                teacher_name = schedule.get("teacher_name", "")
                
                # 获取星期对应的列（1-7对应周一-周日）
                col = day_map.get(day_of_week, 0)
                if col == 0:
                    continue
                
                # 确保period_end >= period_start
                if period_end < period_start:
                    period_end = period_start
                
                # 填充从period_start到period_end的所有节次
                for period in range(period_start - 1, period_end):  # period_start是1-based，转换为0-based
                    if period < 0 or period >= 12:  # 超出范围
                        continue
                    
                    # 构建单元格内容
                    text_parts = [course_name]
                    if credit:
                        text_parts.append(f"{credit}学分")
                    if classroom:
                        text_parts.append(classroom)
                    if teacher_name:
                        text_parts.append(teacher_name)
                    if weeks:
                        text_parts.append(f"({weeks}周)")
                    
                    cell_text = "\n".join(text_parts)
                    
                    # 创建单元格
                    item = QTableWidgetItem(cell_text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(bg_color)
                    item.setForeground(QColor("#1f1f1f"))
                    
                    # 设置字体
                    font = QFont()
                    font.setPointSize(9)
                    item.setFont(font)
                    
                    # 设置对齐方式
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    
                    # 如果该单元格已有内容，合并显示
                    existing_item = self.table.item(period, col)
                    if existing_item:
                        # 合并显示多个课程
                        existing_text = existing_item.text()
                        item.setText(f"{existing_text}\n\n{cell_text}")
                        # 使用更深的颜色表示冲突
                        item.setBackground(QColor(255, 200, 200))
                    
                    self.table.setItem(period, col, item)
        
        # 调整行高以适应内容
        for row in range(12):
            self.table.setRowHeight(row, 80)
    
    def fill_course_list(self):
        """填充课程列表（包括没有课程表信息的课程）"""
        # 按课程分组
        courses_dict = {}
        for item in self.schedule_data:
            course_id = item.get("course_id")
            if not course_id:
                continue
            
            if course_id not in courses_dict:
                courses_dict[course_id] = {
                    "course_id": course_id,
                    "course_name": item.get("course_name", ""),
                    "credit": item.get("credit", ""),
                    "semester": item.get("semester", ""),
                    "teacher_name": item.get("teacher_name", ""),
                    "has_schedule": False,
                    "schedule_count": 0
                }
            
            # 检查是否有课程表信息
            if item.get("schedule_id") and item.get("day_of_week"):
                courses_dict[course_id]["has_schedule"] = True
                courses_dict[course_id]["schedule_count"] += 1
        
        # 转换为列表并排序
        courses_list = list(courses_dict.values())
        courses_list.sort(key=lambda x: (x.get("semester", ""), x.get("course_id", 0)))
        
        # 填充表格
        self.course_list_table.setRowCount(len(courses_list))
        for i, course in enumerate(courses_list):
            course_id = course.get("course_id", "")
            course_name = course.get("course_name", "")
            credit = course.get("credit", "")
            semester = course.get("semester", "")
            teacher_name = course.get("teacher_name", "") or "（未指定）"
            has_schedule = course.get("has_schedule", False)
            schedule_count = course.get("schedule_count", 0)
            
            # 课程表状态
            if has_schedule:
                status_text = f"✅ 已安排 ({schedule_count}个时间段)"
                status_color = QColor("#4caf50")
            else:
                status_text = "⚠️ 未安排时间"
                status_color = QColor("#ff9800")
            
            items = [
                QTableWidgetItem(str(course_id)),
                QTableWidgetItem(course_name),
                QTableWidgetItem(str(credit) if credit else ""),
                QTableWidgetItem(semester),
                QTableWidgetItem(teacher_name),
                QTableWidgetItem(status_text)
            ]
            
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))
            
            # 状态列使用特殊颜色
            items[5].setForeground(status_color)
            
            for col_idx, item in enumerate(items):
                self.course_list_table.setItem(i, col_idx, item)
    
    def update_stats(self):
        """更新统计信息"""
        if not self.schedule_data:
            self.lbl_stats.setText("暂无课程数据")
            return
        
        # 使用字典存储每个课程的学分（避免重复计算）
        course_credits = {}
        course_ids = set()
        courses_with_schedule_set = set()
        
        for item in self.schedule_data:
            course_id = item.get("course_id")
            if course_id:
                course_ids.add(course_id)
                
                # 存储学分（每个课程只存储一次）
                if course_id not in course_credits:
                    credit = item.get("credit")
                    if credit:
                        try:
                            course_credits[course_id] = float(credit)
                        except (ValueError, TypeError):
                            course_credits[course_id] = 0
                    else:
                        course_credits[course_id] = 0
                
                # 检查是否有课程表信息
                if item.get("schedule_id") and item.get("day_of_week"):
                    courses_with_schedule_set.add(course_id)
        
        # 计算总学分
        total_credits = sum(course_credits.values())
        
        courses_with_schedule = len(courses_with_schedule_set)
        courses_without_schedule = len(course_ids) - courses_with_schedule
        
        stats_text = f"共 {len(course_ids)} 门课程 | 总学分: {total_credits:.1f} | "
        stats_text += f"已安排: {courses_with_schedule} | 未安排: {courses_without_schedule}"
        self.lbl_stats.setText(stats_text)
        
        # 统计课程数
        course_ids = set()
        total_credits = 0
        courses_with_schedule = 0
        courses_without_schedule = 0
        
        for item in self.schedule_data:
            course_id = item.get("course_id")
            if course_id:
                course_ids.add(course_id)
                credit = item.get("credit")
                if credit:
                    try:
                        total_credits += float(credit)
                    except (ValueError, TypeError):
                        pass
                
                # 检查是否有课程表信息
                if item.get("schedule_id") and item.get("day_of_week"):
                    if course_id not in [c for c in course_ids if c == course_id]:
                        courses_with_schedule += 1
        
        # 重新统计（避免重复计算）
        courses_with_schedule_set = set()
        for item in self.schedule_data:
            course_id = item.get("course_id")
            if course_id and item.get("schedule_id") and item.get("day_of_week"):
                courses_with_schedule_set.add(course_id)
        
        courses_with_schedule = len(courses_with_schedule_set)
        courses_without_schedule = len(course_ids) - courses_with_schedule
        
        stats_text = f"共 {len(course_ids)} 门课程 | 总学分: {total_credits:.1f} | "
        stats_text += f"已安排: {courses_with_schedule} | 未安排: {courses_without_schedule}"
        self.lbl_stats.setText(stats_text)

