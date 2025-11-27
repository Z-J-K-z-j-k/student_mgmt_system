# client/pages/student_my_courses_page.py
from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHBoxLayout, QLabel, QHeaderView, QLineEdit
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

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索关键词："))
        self.input_keyword = QLineEdit()
        self.input_keyword.setPlaceholderText("课程名 / 课程号")
        self.input_keyword.returnPressed.connect(self.refresh)
        search_layout.addWidget(self.input_keyword)

        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.refresh)
        search_layout.addWidget(self.btn_search)
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
            # 获取成绩记录，其中包含已选课程信息
            resp = self.api.get("/api/scores", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取课程列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        scores = data.get("data", [])
        # 从成绩记录中提取课程信息（通过 course_id 去重，保留 course_id）
        courses_dict = {}
        for score in scores:
            course_id = score.get("course_id")
            course_name = score.get("course_name", "")
            if course_id and course_id not in courses_dict:
                courses_dict[course_id] = {
                    "course_id": course_id,
                    "course_name": course_name,
                }

        # 获取所有课程信息以补充教师和学分信息
        try:
            courses_resp = self.api.get("/api/courses", params={"page": 1, "page_size": 1000})
            courses_data = courses_resp.json()
            if courses_data.get("status") == "ok":
                all_courses = courses_data.get("data", [])
                for course in all_courses:
                    cid = course.get("course_id")
                    if cid in courses_dict:
                        courses_dict[cid]["teacher_name"] = course.get("teacher_name", "")
                        courses_dict[cid]["credit"] = course.get("credit", "")
                        courses_dict[cid]["semester"] = course.get("semester", "")
        except:
            pass  # 如果获取课程详情失败，继续使用已有信息

        my_courses = list(courses_dict.values())
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
            # 使用 partial 避免 lambda 捕获问题
            btn_drop.clicked.connect(partial(self.drop_course, course_id))
            self.table.setCellWidget(i, 6, btn_drop)

        if not my_courses:
            # 不显示提示，让用户知道没有已选课程即可
            pass

    def drop_course(self, course_id: int):
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
            resp = self.api.delete("/api/scores", params={
                "student_id": self.student_id,
                "course_id": course_id
            })
            
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
        self.refresh()

