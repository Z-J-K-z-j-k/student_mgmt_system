# client/pages/student_my_courses_page.py
from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHBoxLayout, QLabel, QHeaderView, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class StudentMyCoursesPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.student_id = None  # 保存 student_id

        layout = QVBoxLayout(self)

        title_layout = QHBoxLayout()
        title = QLabel("📚 已选课程")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._reset_and_refresh)
        title_layout.addWidget(self.btn_refresh)
        layout.addLayout(title_layout)

        search_layout = QVBoxLayout()
        
        # 第一行：关键词搜索
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("搜索关键词："))
        self.input_keyword = QLineEdit()
        self.input_keyword.setPlaceholderText("课程名 / 课程号")
        self.input_keyword.returnPressed.connect(self.refresh)
        row1.addWidget(self.input_keyword)
        row1.addStretch()
        search_layout.addLayout(row1)
        
        # 第二行：筛选条件和按钮
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("学期筛选："))
        self.combo_semester = QComboBox()
        self.combo_semester.setEditable(True)
        self.combo_semester.setPlaceholderText("全部学期")
        self.combo_semester.addItem("")  # 空选项表示全部
        self.combo_semester.setCurrentIndex(0)
        # 确保下拉箭头可见
        self.combo_semester.setStyleSheet("""
            QComboBox::drop-down {
                border: 1px solid #999;
                background-color: #f0f0f0;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #333;
                width: 0;
                height: 0;
            }
        """)
        row2.addWidget(self.combo_semester)
        
        row2.addWidget(QLabel("学分筛选："))
        self.combo_credit = QComboBox()
        self.combo_credit.setEditable(True)
        self.combo_credit.setPlaceholderText("全部学分")
        self.combo_credit.addItem("")  # 空选项表示全部
        self.combo_credit.setCurrentIndex(0)
        # 确保下拉箭头可见
        self.combo_credit.setStyleSheet("""
            QComboBox::drop-down {
                border: 1px solid #999;
                background-color: #f0f0f0;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #333;
                width: 0;
                height: 0;
            }
        """)
        row2.addWidget(self.combo_credit)
        
        row2.addWidget(QLabel("排序方式："))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["课程ID降序", "课程ID升序", "课程名升序", "课程名降序", "学分升序", "学分降序", "学期升序", "学期降序"])
        self.combo_sort.setCurrentIndex(0)
        # 确保下拉箭头可见
        self.combo_sort.setStyleSheet("""
            QComboBox::drop-down {
                border: 1px solid #999;
                background-color: #f0f0f0;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #333;
                width: 0;
                height: 0;
            }
        """)
        row2.addWidget(self.combo_sort)
        
        row2.addStretch()
        
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.refresh)
        row2.addWidget(self.btn_search)
        search_layout.addLayout(row2)
        
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(7)  # 添加操作列
        self.table.setHorizontalHeaderLabels(
            ["ID", "课程号", "课程名", "任课教师", "学分", "学期", "操作"]
        )

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        # 初始化：获取 student_id
        self.init_student_info()
        self.refresh()

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

    def refresh(self):
        """刷新已选课程列表"""
        if not self.student_id:
            self.init_student_info()
        
        if not self.student_id:
            QMessageBox.warning(self, "错误", "无法获取学生ID")
            return

        try:
            params = {"student_id": str(self.student_id)}
            keyword = self.input_keyword.text().strip() if hasattr(self, "input_keyword") else ""
            if keyword:
                params["course_name"] = keyword
            
            # 添加学期筛选
            semester = self.combo_semester.currentText().strip() if hasattr(self, "combo_semester") else ""
            if semester:
                params["semester"] = semester
            
            # 学分筛选在客户端进行
            credit_filter = self.combo_credit.currentText().strip() if hasattr(self, "combo_credit") else ""
            
            # 直接从course_selection表获取已选课程列表
            resp = self.api.get("/api/student/my-courses", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        my_courses = data.get("data", [])
        
        # 客户端学分筛选
        if hasattr(self, "combo_credit"):
            credit_filter = self.combo_credit.currentText().strip()
            if credit_filter:
                try:
                    credit_value = int(credit_filter)
                    my_courses = [c for c in my_courses if c.get("credit") == credit_value]
                except ValueError:
                    # 如果不是数字，尝试模糊匹配
                    my_courses = [c for c in my_courses if str(c.get("credit", "")).find(credit_filter) >= 0]
        
        # 客户端排序
        if hasattr(self, "combo_sort"):
            sort_option = self.combo_sort.currentText()
            if "课程ID" in sort_option:
                reverse = "降序" in sort_option
                my_courses.sort(key=lambda x: x.get("course_id", 0), reverse=reverse)
            elif "课程名" in sort_option:
                reverse = "降序" in sort_option
                my_courses.sort(key=lambda x: x.get("course_name", ""), reverse=reverse)
            elif "学分" in sort_option:
                reverse = "降序" in sort_option
                my_courses.sort(key=lambda x: x.get("credit", 0) or 0, reverse=reverse)
            elif "学期" in sort_option:
                reverse = "降序" in sort_option
                my_courses.sort(key=lambda x: x.get("semester", ""), reverse=reverse)
        
        # 更新学期下拉框选项（从课程数据中提取所有学期）
        if hasattr(self, "combo_semester"):
            current_semester = self.combo_semester.currentText().strip()
            semesters = set()
            for course in my_courses:
                sem = course.get("semester", "").strip()
                if sem:
                    semesters.add(sem)
            
            # 保存当前选择
            self.combo_semester.clear()
            self.combo_semester.addItem("")  # 全部学期
            for sem in sorted(semesters):
                self.combo_semester.addItem(sem)
            
            # 恢复之前的选择
            index = self.combo_semester.findText(current_semester)
            if index >= 0:
                self.combo_semester.setCurrentIndex(index)
            else:
                self.combo_semester.setCurrentIndex(0)
        
        # 更新学分下拉框选项
        if hasattr(self, "combo_credit"):
            current_credit = self.combo_credit.currentText().strip()
            credits = set()
            for course in my_courses:
                credit = course.get("credit")
                if credit is not None:
                    credits.add(str(credit))
            
            # 保存当前选择
            self.combo_credit.clear()
            self.combo_credit.addItem("")  # 全部学分
            for credit in sorted(credits, key=lambda x: int(x) if x.isdigit() else 0):
                self.combo_credit.addItem(credit)
            
            # 恢复之前的选择
            index = self.combo_credit.findText(current_credit)
            if index >= 0:
                self.combo_credit.setCurrentIndex(index)
            else:
                self.combo_credit.setCurrentIndex(0)
        
        self.table.setRowCount(len(my_courses))
        for i, course in enumerate(my_courses):
            course_id = course.get("course_id")
            items = [
                QTableWidgetItem(str(course_id)),
                QTableWidgetItem(str(course_id)),  # course_no 不存在，用 course_id 代替
                QTableWidgetItem(course.get("course_name", "")),
                QTableWidgetItem(course.get("teacher_name", "")),
                QTableWidgetItem(str(course.get("credit", ""))),
                QTableWidgetItem(course.get("semester", "")),
            ]
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))

            for col_idx, item in enumerate(items):
                self.table.setItem(i, col_idx, item)

            # 添加退课按钮
            btn_drop = QPushButton("退课")
            btn_drop.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            # 使用 partial 传递 course_id 和 semester，避免 lambda 捕获问题
            semester = course.get("semester", "")
            btn_drop.clicked.connect(partial(self.drop_course, course_id, semester))
            self.table.setCellWidget(i, 6, btn_drop)

        if not my_courses:
            # 不显示提示，让用户知道没有已选课程即可
            pass

    def drop_course(self, course_id: int, semester: str = ""):
        """退课"""
        try:
            if not self.student_id:
                QMessageBox.warning(self, "错误", "无法获取学生ID")
                return

            reply = QMessageBox.question(
                self, "确认", "确定要退选该课程吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # 使用 DELETE 方法，通过查询参数传递
            params = {
                "student_id": self.student_id,
                "course_id": course_id
            }
            # 如果提供了学期信息，也传递过去
            if semester:
                params["semester"] = semester
            
            resp = self.api.delete("/api/scores", params=params)
            
            if resp.status_code != 200:
                try:
                    data = resp.json()
                    msg = data.get("msg", "退课失败")
                except:
                    msg = f"退课失败：{resp.text[:200]}"
                QMessageBox.warning(self, "错误", msg)
                return
            
            data = resp.json()
            if data.get("status") == "ok":
                # 先刷新列表
                try:
                    self.refresh()
                except Exception as e:
                    print(f"刷新失败：{e}")
                
                # 显示成功消息（使用 None 作为父对象，避免依赖 self）
                try:
                    msg_box = QMessageBox()
                    msg_box.setWindowTitle("成功")
                    msg_box.setText("退课成功")
                    msg_box.setIcon(QMessageBox.Icon.Information)
                    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg_box.exec()
                except Exception:
                    pass
            else:
                try:
                    msg_box = QMessageBox()
                    msg_box.setWindowTitle("错误")
                    msg_box.setText(data.get("msg", "退课失败"))
                    msg_box.setIcon(QMessageBox.Icon.Warning)
                    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg_box.exec()
                except Exception:
                    pass
        except RuntimeError:
            # 对象已被删除，忽略错误
            pass
        except Exception as e:
            try:
                QMessageBox.critical(self, "错误", f"退课失败：{str(e)}")
            except RuntimeError:
                # 对象已被删除，忽略错误
                pass

    def _reset_and_refresh(self):
        """清空搜索条件并刷新"""
        if hasattr(self, "input_keyword"):
            self.input_keyword.clear()
        if hasattr(self, "combo_semester"):
            self.combo_semester.setCurrentIndex(0)
        if hasattr(self, "combo_credit"):
            self.combo_credit.setCurrentIndex(0)
        if hasattr(self, "combo_sort"):
            self.combo_sort.setCurrentIndex(0)
        self.refresh()

