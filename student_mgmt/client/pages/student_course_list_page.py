# client/pages/student_course_list_page.py
from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QLabel, QHeaderView, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient

class StudentCourseListPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.student_id = None  # 保存 student_id
        self.selected_course_ids = set()  # 已选课程ID集合

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # 标题
        title = QLabel("📖 全部课程")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        layout.addWidget(title)

        # 搜索与刷新
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("搜索关键词："))
        self.input_keyword = QLineEdit()
        self.input_keyword.setPlaceholderText("课程名 / 课程号 / 教师名")
        self.input_keyword.returnPressed.connect(self.refresh)
        control_layout.addWidget(self.input_keyword)

        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.refresh)
        control_layout.addWidget(self.btn_search)

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._reset_and_refresh)
        control_layout.addWidget(self.btn_refresh)
        layout.addLayout(control_layout)

        # 课程表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "课程号", "课程名", "任课教师", "学分", "学期", "操作"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        # 初始化：获取 student_id 和已选课程
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

    def load_selected_courses(self):
        """加载已选课程ID列表"""
        if not self.student_id:
            return
        
        try:
            resp = self.api.get("/api/scores", params={"student_id": str(self.student_id)})
            data = resp.json()
            if data.get("status") == "ok":
                scores = data.get("data", [])
                self.selected_course_ids = {s.get("course_id") for s in scores if s.get("course_id")}
        except Exception as e:
            print(f"获取已选课程失败：{e}")

    def refresh(self):
        """刷新课程列表"""
        try:
            if not self.student_id:
                self.init_student_info()
            
            # 加载已选课程
            self.load_selected_courses()

            try:
                params = {"page": 1, "page_size": 1000}
                keyword = self.input_keyword.text().strip() if hasattr(self, "input_keyword") else ""
                if keyword:
                    params["keyword"] = keyword
                resp = self.api.get("/api/courses", params=params)
                data = resp.json()
            except Exception as e:
                try:
                    QMessageBox.critical(self, "错误", f"获取课程列表失败：{e}")
                except RuntimeError:
                    pass
                return

            if data.get("status") != "ok":
                try:
                    QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
                except RuntimeError:
                    pass
                return

            courses = data.get("data", [])
            self.table.setRowCount(len(courses))

            for i, course in enumerate(courses):
                course_id = course.get("course_id")
                
                # 表格数据
                items = [
                    QTableWidgetItem(str(course_id)),
                    QTableWidgetItem(str(course_id)),  # course_no 不存在，用 course_id 代替
                    QTableWidgetItem(course.get("course_name", "")),
                    QTableWidgetItem(course.get("teacher_name", "")),
                    QTableWidgetItem(str(course.get("credit", ""))),
                    QTableWidgetItem(course.get("semester", "")),
                ]
                
                # 设置所有单元格为只读
                for item in items:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setForeground(QColor("#1f1f1f"))
                
                for col_idx, item in enumerate(items):
                    self.table.setItem(i, col_idx, item)

                # 添加选课按钮
                btn_select = QPushButton("选课" if course_id not in self.selected_course_ids else "已选")
                btn_select.setEnabled(course_id not in self.selected_course_ids)
                btn_select.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:disabled {
                        background-color: #cccccc;
                        color: #666666;
                    }
                """)
                # 使用 partial 避免 lambda 捕获问题
                btn_select.clicked.connect(partial(self.select_course, course_id))
                self.table.setCellWidget(i, 6, btn_select)
        except RuntimeError:
            # 对象已被删除，忽略错误
            pass
        except Exception as e:
            # 其他错误也静默处理，避免崩溃
            print(f"刷新课程列表时出错：{e}")

    def select_course(self, course_id: int):
        """选课"""
        try:
            if not self.student_id:
                try:
                    QMessageBox.warning(self, "错误", "无法获取学生ID，请刷新页面重试")
                except RuntimeError:
                    pass
                return

            try:
                reply = QMessageBox.question(
                    self, "确认", f"确定要选择该课程吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            except RuntimeError:
                # 对象已被删除，直接返回
                return

            resp = self.api.post("/api/scores", json={
                "student_id": self.student_id,
                "course_id": course_id
            })
            
            if resp.status_code != 200:
                try:
                    data = resp.json()
                    msg = data.get("msg", "选课失败")
                except:
                    msg = f"选课失败：{resp.text[:200]}"
                try:
                    QMessageBox.warning(self, "错误", msg)
                except RuntimeError:
                    pass
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
                    msg_box.setText("选课成功")
                    msg_box.setIcon(QMessageBox.Icon.Information)
                    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg_box.exec()
                except Exception:
                    pass
            else:
                try:
                    msg_box = QMessageBox()
                    msg_box.setWindowTitle("错误")
                    msg_box.setText(data.get("msg", "选课失败"))
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
                QMessageBox.critical(self, "错误", f"选课失败：{str(e)}")
            except RuntimeError:
                # 对象已被删除，忽略错误
                pass
            except Exception:
                # 其他异常也忽略，避免崩溃
                print(f"选课时出错：{e}")

    def _reset_and_refresh(self):
        """清空搜索条件并刷新"""
        if hasattr(self, "input_keyword"):
            self.input_keyword.clear()
        self.refresh()

