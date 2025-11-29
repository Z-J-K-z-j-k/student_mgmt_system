# client/pages/scores_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QLineEdit, QPushButton, QMessageBox, QInputDialog,
    QFileDialog, QLabel, QCheckBox, QDialog, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..utils.api_client import APIClient
import csv
from datetime import datetime


class ScoresPage(QWidget):
    def __init__(self, api: APIClient, role: str, user_id: int):
        super().__init__()
        self.api = api
        self.role = role
        self.user_id = user_id
        self.current_scores = []

        layout = QVBoxLayout(self)

        # 搜索区域
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索："))
        
        self.ed_stu_id = QLineEdit()
        self.ed_stu_id.setPlaceholderText("按学生ID（可选）")
        self.ed_stu_id.setMaximumWidth(150)
        search_layout.addWidget(self.ed_stu_id)
        
        self.ed_course_id = QLineEdit()
        self.ed_course_id.setPlaceholderText("按课程ID（可选）")
        self.ed_course_id.setMaximumWidth(150)
        search_layout.addWidget(self.ed_course_id)
        
        self.ed_course_name = QLineEdit()
        self.ed_course_name.setPlaceholderText("按课程名（可选）")
        self.ed_course_name.setMaximumWidth(200)
        search_layout.addWidget(self.ed_course_name)
        
        self.btn_filter = QPushButton("搜索")
        self.btn_filter.clicked.connect(self.refresh)
        search_layout.addWidget(self.btn_filter)
        
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self.clear_search)
        search_layout.addWidget(self.btn_clear)
        
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # 操作按钮区域（仅管理员）
        if role == "admin":
            admin_layout = QHBoxLayout()
            admin_layout.addWidget(QLabel("管理员操作："))
            
            self.btn_refresh = QPushButton("刷新")
            self.btn_refresh.clicked.connect(self.refresh)
            admin_layout.addWidget(self.btn_refresh)
            
            self.btn_edit = QPushButton("修改所选成绩")
            self.btn_edit.clicked.connect(self.edit_score)
            admin_layout.addWidget(self.btn_edit)
            
            self.btn_batch_import = QPushButton("批量导入")
            self.btn_batch_import.clicked.connect(self.batch_import)
            admin_layout.addWidget(self.btn_batch_import)
            
            self.btn_cleanup = QPushButton("清理异常数据")
            self.btn_cleanup.clicked.connect(self.cleanup_abnormal)
            admin_layout.addWidget(self.btn_cleanup)
            
            admin_layout.addStretch()
            layout.addLayout(admin_layout)
        elif role == "teacher":
            # 教师只能修改成绩
            teacher_layout = QHBoxLayout()
            self.btn_edit = QPushButton("修改所选成绩")
            self.btn_edit.clicked.connect(self.edit_score)
            teacher_layout.addWidget(self.btn_edit)
            teacher_layout.addStretch()
            layout.addLayout(teacher_layout)

        # 成绩表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "学号", "姓名", "课程", "成绩", "学期"]
        )
        from PyQt6.QtWidgets import QHeaderView

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        quick_filter_layout = QHBoxLayout()
        quick_filter_layout.addWidget(QLabel("表格检索："))

        self.quick_filter_input = QLineEdit()
        self.quick_filter_input.setPlaceholderText("输入学号/姓名/课程/学期关键字快速筛选")
        self.quick_filter_input.textChanged.connect(self.apply_quick_filter)
        quick_filter_layout.addWidget(self.quick_filter_input)
        quick_filter_layout.addStretch()

        layout.addLayout(quick_filter_layout)
        layout.addWidget(self.table)

        self.refresh()

    def clear_search(self):
        """清空搜索条件"""
        self.ed_stu_id.clear()
        self.ed_course_id.clear()
        self.ed_course_name.clear()
        self.refresh()

    def refresh(self):
        """刷新成绩列表"""
        params = {}
        if self.ed_stu_id.text().strip():
            params["student_id"] = self.ed_stu_id.text().strip()
        if self.ed_course_id.text().strip():
            params["course_id"] = self.ed_course_id.text().strip()
        if self.ed_course_name.text().strip():
            params["course_name"] = self.ed_course_name.text().strip()

        try:
            # 教师角色使用专用接口
            if self.role == "teacher":
                resp = self.api.get("/api/teacher/scores", params=params)
            else:
                resp = self.api.get("/api/scores", params=params)
            
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", f"服务器返回错误：{resp.status_code}")
                except:
                    error_msg = f"服务器返回错误：{resp.status_code}"
                QMessageBox.critical(self, "错误", error_msg)
                return
                
            data = resp.json()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取成绩失败：{e}")
            return

        if data.get("status") != "ok":
            QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            return

        self.current_scores = data.get("data", [])
        self.apply_quick_filter()

    def apply_quick_filter(self):
        """根据关键字快速筛选表格数据"""
        if not hasattr(self, "current_scores"):
            return

        keyword = self.quick_filter_input.text().strip().lower()
        if not keyword:
            filtered = self.current_scores
        else:
            def match(item):
                targets = [
                    str(item.get("student_id", "")),
                    item.get("student_name", ""),
                    item.get("course_name", ""),
                    str(item.get("score", "")),
                    str(item.get("semester", "")),
                ]
                return any(keyword in (t or "").lower() for t in targets)

            filtered = [score for score in self.current_scores if match(score)]

        self.populate_scores(filtered)

    def populate_scores(self, scores):
        """渲染成绩表格"""
        self.table.setRowCount(len(scores))
        for i, s in enumerate(scores):
            score_value = s.get("score")
            score_text = str(score_value) if score_value is not None else "None"
            
            semester_value = s.get("semester")
            semester_text = str(semester_value) if semester_value is not None else "None"
            
            items = [
                QTableWidgetItem(str(s.get("score_id", ""))),
                QTableWidgetItem(str(s.get("student_id", ""))),
                QTableWidgetItem(s.get("student_name", "")),
                QTableWidgetItem(s.get("course_name", "")),
                QTableWidgetItem(score_text),
                QTableWidgetItem(semester_text),
            ]
            # 设置所有单元格为只读，并确保文本颜色可见
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))
            
            for col_idx, item in enumerate(items):
                self.table.setItem(i, col_idx, item)

    def edit_score(self):
        """修改成绩"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一行")
            return
        
        eid = int(self.table.item(row, 0).text())
        old_score_text = self.table.item(row, 4).text()
        
        # 处理成绩为None的情况
        try:
            old_score = float(old_score_text) if old_score_text != "None" else 0.0
        except ValueError:
            old_score = 0.0
        
        new_score, ok = QInputDialog.getDouble(
            self, "修改成绩", "新成绩：", old_score, 0, 100, 1
        )
        if not ok:
            return

        try:
            resp = self.api.put(f"/api/scores/{eid}", json={"score": new_score})
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", f"服务器返回错误：{resp.status_code}")
                except:
                    error_msg = f"服务器返回错误：{resp.status_code}"
                QMessageBox.critical(self, "错误", error_msg)
                return
            
            data = resp.json()
            if data.get("status") == "ok":
                QMessageBox.information(self, "成功", "成绩修改成功")
                self.refresh()
            else:
                QMessageBox.warning(self, "错误", data.get("msg", "修改失败"))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修改失败：{e}")

    def batch_import(self):
        """批量导入成绩（CSV文件）"""
        if self.role != "admin":
            return
        
        # 选择CSV文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # 读取CSV文件
            scores_data = []
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        student_id = int(row.get("student_id", "").strip())
                        course_id = int(row.get("course_id", "").strip())
                        score_str = row.get("score", "").strip()
                        score = float(score_str) if score_str else None
                        exam_date_str = row.get("exam_date", "").strip()
                        exam_date = exam_date_str if exam_date_str else None
                        
                        scores_data.append({
                            "student_id": student_id,
                            "course_id": course_id,
                            "score": score,
                            "exam_date": exam_date
                        })
                    except (ValueError, KeyError) as e:
                        QMessageBox.warning(
                            self, "警告", 
                            f"跳过无效行：{row}\n错误：{str(e)}"
                        )
                        continue
            
            if not scores_data:
                QMessageBox.warning(self, "提示", "CSV文件中没有有效数据")
                return
            
            # 确认对话框
            reply = QMessageBox.question(
                self, "确认导入",
                f"准备导入 {len(scores_data)} 条成绩记录，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # 发送批量导入请求
            resp = self.api.post("/api/scores/batch", json={"scores": scores_data})
            
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", f"服务器返回错误：{resp.status_code}")
                except:
                    error_msg = f"服务器返回错误：{resp.status_code}"
                QMessageBox.critical(self, "错误", error_msg)
                return
            
            data = resp.json()
            if data.get("status") == "ok":
                success_count = data.get("success_count", 0)
                error_count = data.get("error_count", 0)
                errors = data.get("errors", [])
                
                msg = f"导入完成！\n成功：{success_count} 条\n失败：{error_count} 条"
                if errors:
                    msg += f"\n\n错误详情（最多显示20条）：\n" + "\n".join(errors[:20])
                
                QMessageBox.information(self, "导入结果", msg)
                self.refresh()
            else:
                QMessageBox.warning(self, "错误", data.get("msg", "导入失败"))
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def cleanup_abnormal(self):
        """批量清理异常数据"""
        if self.role != "admin":
            return
        
        # 创建清理选项对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("清理异常数据")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        
        checkbox_empty = QCheckBox("清理空成绩（score为NULL的记录）")
        checkbox_empty.setChecked(True)
        checkbox_empty.setStyleSheet("color: black;")
        form_layout.addRow(checkbox_empty)
        
        checkbox_duplicates = QCheckBox("清理重复成绩（同一学生同一课程的多条记录，保留最新的）")
        checkbox_duplicates.setChecked(True)
        checkbox_duplicates.setStyleSheet("color: black;")
        form_layout.addRow(checkbox_duplicates)
        
        layout.addLayout(form_layout)
        
        # 说明文本（两行分别设置）
        info_label1 = QLabel("注意：此操作将永久删除数据，请谨慎操作！")
        info_label1.setStyleSheet("color: black;")
        layout.addWidget(info_label1)
        
        info_label2 = QLabel("建议在执行前先备份数据库。")
        info_label2.setStyleSheet("color: black;")
        layout.addWidget(info_label2)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        cleanup_empty = checkbox_empty.isChecked()
        cleanup_duplicates = checkbox_duplicates.isChecked()
        
        if not cleanup_empty and not cleanup_duplicates:
            QMessageBox.warning(self, "提示", "请至少选择一种清理类型")
            return
        
        # 二次确认
        reply = QMessageBox.question(
            self, "确认清理",
            "确定要清理异常数据吗？此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            resp = self.api.post("/api/scores/cleanup", json={
                "cleanup_empty": cleanup_empty,
                "cleanup_duplicates": cleanup_duplicates
            })
            
            if resp.status_code != 200:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", f"服务器返回错误：{resp.status_code}")
                except:
                    error_msg = f"服务器返回错误：{resp.status_code}"
                QMessageBox.critical(self, "错误", error_msg)
                return
            
            data = resp.json()
            if data.get("status") == "ok":
                deleted_count = data.get("deleted_count", 0)
                details = data.get("details", [])
                
                msg = f"清理完成！\n共删除 {deleted_count} 条记录\n\n"
                msg += "\n".join(details)
                
                QMessageBox.information(self, "清理结果", msg)
                self.refresh()
            else:
                QMessageBox.warning(self, "错误", data.get("msg", "清理失败"))
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清理失败：{e}")
