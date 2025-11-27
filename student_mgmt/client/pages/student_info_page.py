# client/pages/student_info_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout,
    QMessageBox, QPushButton, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt
from ..utils.api_client import APIClient

class StudentInfoPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.student_id = None  # 保存 student_id 用于更新
        self.is_editing = False  # 编辑状态标志

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # 标题和按钮区域
        title_layout = QHBoxLayout()
        title = QLabel("🧍 个人信息")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # 编辑/保存按钮
        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_edit.clicked.connect(self.toggle_edit_mode)
        
        self.btn_save = QPushButton("保存")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.btn_save.clicked.connect(self.save_info)
        self.btn_save.setVisible(False)
        
        title_layout.addWidget(self.btn_edit)
        title_layout.addWidget(self.btn_save)
        layout.addLayout(title_layout)

        # 信息显示区域
        form = QFormLayout()
        form.setSpacing(15)

        # 只读字段（使用 QLabel）
        self.lbl_name = QLabel()
        self.lbl_name.setStyleSheet("color: #1f1f1f; padding: 5px;")
        self.lbl_no = QLabel()
        self.lbl_no.setStyleSheet("color: #1f1f1f; padding: 5px;")
        self.lbl_gender = QLabel()
        self.lbl_gender.setStyleSheet("color: #1f1f1f; padding: 5px;")
        self.lbl_major = QLabel()
        self.lbl_major.setStyleSheet("color: #1f1f1f; padding: 5px;")
        self.lbl_class = QLabel()
        self.lbl_class.setStyleSheet("color: #1f1f1f; padding: 5px;")

        # 可编辑字段（只允许修改电话和邮箱）
        self.ed_phone = QLineEdit()
        self.ed_phone.setStyleSheet("padding: 5px;")
        self.ed_phone.setEnabled(False)
        
        self.ed_email = QLineEdit()
        self.ed_email.setStyleSheet("padding: 5px;")
        self.ed_email.setEnabled(False)

        form.addRow("姓名：", self.lbl_name)
        form.addRow("学号：", self.lbl_no)
        form.addRow("性别：", self.lbl_gender)
        form.addRow("专业：", self.lbl_major)
        form.addRow("班级：", self.lbl_class)
        form.addRow("电话：", self.ed_phone)
        form.addRow("邮箱：", self.ed_email)

        layout.addLayout(form)
        layout.addStretch()

        # 延迟刷新，确保窗口完全初始化后再加载数据
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self.refresh)

    def toggle_edit_mode(self):
        """切换编辑模式"""
        self.is_editing = not self.is_editing
        if self.is_editing:
            # 进入编辑模式（只允许编辑电话和邮箱）
            self.ed_phone.setEnabled(True)
            self.ed_email.setEnabled(True)
            self.btn_edit.setVisible(False)
            self.btn_save.setVisible(True)
        else:
            # 退出编辑模式（取消编辑）
            self.ed_phone.setEnabled(False)
            self.ed_email.setEnabled(False)
            self.btn_edit.setVisible(True)
            self.btn_save.setVisible(False)
            # 恢复原始数据
            self.refresh()

    def save_info(self):
        """保存学生信息"""
        if not self.student_id:
            QMessageBox.warning(self, "错误", "无法获取学生ID")
            return
        
        # 收集数据（只更新电话和邮箱）
        update_data = {
            "phone": self.ed_phone.text().strip(),
            "email": self.ed_email.text().strip()
        }
        
        # 验证必填字段（如果需要）
        # 这里可以根据需要添加验证逻辑
        
        try:
            # 调用 API 更新
            resp = self.api.put(f"/api/students/{self.student_id}", json=update_data)
            
            # 检查响应状态码
            if resp.status_code != 200:
                QMessageBox.critical(self, "错误", f"服务器返回错误：{resp.status_code}\n{resp.text}")
                return
            
            # 尝试解析 JSON
            try:
                data = resp.json()
            except ValueError as e:
                QMessageBox.critical(self, "错误", f"服务器返回格式错误：{resp.text[:200]}")
                return
            
            if data.get("status") == "ok":
                QMessageBox.information(self, "成功", "个人信息更新成功")
                # 退出编辑模式
                self.is_editing = False
                self.ed_phone.setEnabled(False)
                self.ed_email.setEnabled(False)
                self.btn_edit.setVisible(True)
                self.btn_save.setVisible(False)
                # 刷新数据
                self.refresh()
            else:
                QMessageBox.warning(self, "错误", data.get("msg", "更新失败"))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")

    def refresh(self):
        """刷新学生信息"""
        try:
            # 检查 API 客户端是否有效
            if not self.api or not hasattr(self.api, 'get'):
                try:
                    self.lbl_name.setText("API 客户端未初始化")
                except RuntimeError:
                    pass
                return
            
            # 调用 API
            resp = self.api.get("/api/students", params={"page": 1, "page_size": 1000})
            
            # 检查响应状态码
            if resp.status_code != 200:
                try:
                    self.lbl_name.setText(f"服务器错误：{resp.status_code}")
                except RuntimeError:
                    pass
                return
            
            # 安全地解析 JSON
            try:
                data = resp.json()
            except (ValueError, AttributeError) as e:
                try:
                    self.lbl_name.setText(f"响应解析失败：{str(e)}")
                except RuntimeError:
                    pass
                return
                
        except Exception as e:
            # 安全地设置错误信息，避免在初始化时显示消息框导致闪退
            try:
                error_msg = str(e)
                if "Connection" in error_msg or "timeout" in error_msg.lower():
                    self.lbl_name.setText("无法连接到服务器，请检查服务器是否运行")
                else:
                    self.lbl_name.setText(f"获取学生信息失败：{error_msg}")
            except RuntimeError:
                # 对象已被删除，忽略
                pass
            return

        # 检查响应数据格式
        if not isinstance(data, dict):
            try:
                self.lbl_name.setText("服务器返回数据格式错误")
            except RuntimeError:
                pass
            return

        if data.get("status") != "ok":
            # 安全地设置错误信息
            try:
                self.lbl_name.setText(f"错误：{data.get('msg', '未知错误')}")
            except RuntimeError:
                pass
            return

        # 查找当前用户的学生信息
        students = data.get("data", [])
        if not isinstance(students, list):
            try:
                self.lbl_name.setText("数据格式错误：学生列表不是数组")
            except RuntimeError:
                pass
            return

        student = None
        for s in students:
            if not isinstance(s, dict):
                continue
            # 检查 student_id 或 user_id 是否匹配
            if s.get("student_id") == self.user_id or s.get("user_id") == self.user_id:
                student = s
                break

        try:
            if student:
                self.student_id = student.get("student_id")
                self.lbl_name.setText(student.get("name", "") or "未知")
                self.lbl_no.setText(str(student.get("student_id", "") or ""))
                self.lbl_gender.setText(student.get("gender", "") or "未知")
                self.lbl_major.setText(student.get("major", "") or "未知")
                self.lbl_class.setText(student.get("class_name", "") or "未知")
                
                # 设置可编辑字段的值
                self.ed_phone.setText(student.get("phone", "") or "")
                self.ed_email.setText(student.get("email", "") or "")
            else:
                self.lbl_name.setText("未找到学生信息")
                # 不显示消息框，避免在初始化时导致闪退
                # 只在用户主动刷新时显示提示
        except RuntimeError:
            # 对象已被删除，忽略
            pass
        except Exception as e:
            # 捕获其他可能的异常
            try:
                self.lbl_name.setText(f"显示信息时出错：{str(e)}")
            except RuntimeError:
                pass

