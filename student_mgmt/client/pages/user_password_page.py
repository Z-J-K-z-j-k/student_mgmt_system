# client/pages/user_password_page.py
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QDialog,
    QFormLayout, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient


class PasswordChangeDialog(QDialog):
    """修改密码对话框"""
    def __init__(self, parent, user_id: int, username: str):
        super().__init__(parent)
        self.user_id = user_id
        self.username = username
        self.setWindowTitle(f"修改密码 - {username}")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        # 原密码
        self.ed_old_password = QLineEdit()
        self.ed_old_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("原密码*：", self.ed_old_password)
        
        # 新密码
        self.ed_new_password = QLineEdit()
        self.ed_new_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("新密码*：", self.ed_new_password)
        
        # 新密码确认
        self.ed_confirm_password = QLineEdit()
        self.ed_confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("新密码确认*：", self.ed_confirm_password)
        
        # 按钮
        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)
        layout.addRow(btn_box)
    
    def accept(self):
        """验证并接受"""
        old_password = self.ed_old_password.text().strip()
        new_password = self.ed_new_password.text().strip()
        confirm_password = self.ed_confirm_password.text().strip()
        
        if not old_password:
            QMessageBox.warning(self, "验证失败", "原密码不能为空")
            return
        
        if not new_password:
            QMessageBox.warning(self, "验证失败", "新密码不能为空")
            return
        
        if new_password != confirm_password:
            QMessageBox.warning(self, "验证失败", "新密码和确认密码不一致")
            return
        
        if len(new_password) < 6:
            QMessageBox.warning(self, "验证失败", "新密码长度至少为6位")
            return
        
        super().accept()
    
    def get_passwords(self):
        """获取密码"""
        return {
            "old_password": self.ed_old_password.text().strip(),
            "new_password": self.ed_new_password.text().strip()
        }


class UserPasswordPage(QWidget):
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
        self.ed_keyword.setPlaceholderText("关键字（用户名/用户ID）")
        self.ed_keyword.returnPressed.connect(self.refresh)
        row1.addWidget(QLabel("关键字："))
        row1.addWidget(self.ed_keyword)
        row1.addStretch()
        
        # 第二行：详细搜索条件
        row2 = QHBoxLayout()
        self.ed_user_id = QLineEdit()
        self.ed_user_id.setPlaceholderText("用户ID（精确）")
        self.ed_username = QLineEdit()
        self.ed_username.setPlaceholderText("用户名（模糊）")
        self.combo_role = QComboBox()
        self.combo_role.addItems(["", "student", "teacher", "admin"])
        self.combo_role.setCurrentIndex(0)
        self.combo_role.setPlaceholderText("角色")
        
        row2.addWidget(QLabel("用户ID："))
        row2.addWidget(self.ed_user_id)
        row2.addWidget(QLabel("用户名："))
        row2.addWidget(self.ed_username)
        row2.addWidget(QLabel("角色："))
        row2.addWidget(self.combo_role)
        
        # 第三行：按钮
        row3 = QHBoxLayout()
        self.btn_search = QPushButton("搜索")
        self.btn_reset = QPushButton("重置")
        self.btn_search.clicked.connect(self.refresh)
        self.btn_reset.clicked.connect(self.reset_search)
        
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
        headers = ["用户ID", "用户名", "角色", "创建时间", "操作"]
        self.table.setHorizontalHeaderLabels(headers)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 设置默认行高
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.verticalHeader().setMinimumSectionSize(50)

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
        self.ed_user_id.clear()
        self.ed_username.clear()
        self.combo_role.setCurrentIndex(0)
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
            user_id = self.ed_user_id.text().strip()
            username = self.ed_username.text().strip()
            role = self.combo_role.currentText().strip()
            
            if user_id:
                try:
                    params["user_id"] = int(user_id)
                except ValueError:
                    QMessageBox.warning(self, "错误", "用户ID必须是数字")
                    return
            if username:
                params["username"] = username
            if role:
                params["role"] = role
        
        try:
            resp = self.api.get("/api/users", params=params)
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取用户列表失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.total = data["total"]
        self.render_table(data["data"])
        total_pages = max(1, math.ceil(self.total / self.page_size))
        self.lbl_page.setText(f"第 {self.page} / {total_pages} 页，共 {self.total} 条")

    def render_table(self, users):
        self.table.setRowCount(len(users))
        
        for row_idx, u in enumerate(users):
            # 设置每一行的高度
            self.table.setRowHeight(row_idx, 50)
            
            # 创建单元格
            created_at = u.get("created_at", "")
            if created_at:
                # 格式化时间
                try:
                    from datetime import datetime
                    if isinstance(created_at, str):
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            items = [
                QTableWidgetItem(str(u.get("user_id", ""))),
                QTableWidgetItem(u.get("username", "")),
                QTableWidgetItem(u.get("role", "")),
                QTableWidgetItem(created_at),
            ]
            
            # 设置所有单元格为只读
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))
            
            for col_idx, item in enumerate(items):
                self.table.setItem(row_idx, col_idx, item)
            
            # 添加操作按钮
            btn_layout = QHBoxLayout()
            btn_change = QPushButton("修改密码")
            
            # 设置按钮样式
            btn_change.setStyleSheet("""
                QPushButton {
                    background-color: #3a8dd0;
                    color: #ffffff;
                    border: none;
                    border-radius: 5px;
                    padding: 6px 16px 10px 16px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 80px;
                    min-height: 32px;
                }
                QPushButton:hover {
                    background-color: #5BA0FF;
                }
                QPushButton:pressed {
                    background-color: #2F74D0;
                }
            """)
            
            btn_change.clicked.connect(lambda checked, uid=u.get("user_id"), uname=u.get("username"): 
                                      self.change_password(uid, uname))
            
            btn_layout.addWidget(btn_change)
            btn_layout.setContentsMargins(5, 5, 5, 5)
            btn_layout.setSpacing(5)
            
            widget = QWidget()
            widget.setLayout(btn_layout)
            self.table.setCellWidget(row_idx, 4, widget)

    def change_password(self, user_id: int, username: str):
        """修改密码"""
        dialog = PasswordChangeDialog(self, user_id, username)
        if dialog.exec():
            passwords = dialog.get_passwords()
            try:
                resp = self.api.put(f"/api/users/{user_id}/password", json=passwords)
                data = resp.json()
                
                if data.get("status") == "ok":
                    QMessageBox.information(self, "成功", "密码修改成功")
                else:
                    QMessageBox.warning(self, "错误", data.get("msg", "密码修改失败"))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"修改密码失败：{e}")

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.refresh()

    def next_page(self):
        total_pages = max(1, math.ceil(self.total / self.page_size))
        if self.page < total_pages:
            self.page += 1
            self.refresh()

