# client/pages/student_my_grades_page.py
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHBoxLayout, QLabel, QComboBox,
    QFileDialog, QDialog, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPixmap
from ..utils.api_client import APIClient
import requests

class GradeChartDialog(QDialog):
    """成绩趋势图表对话框"""
    def __init__(self, parent, scores_data):
        super().__init__(parent)
        self.setWindowTitle("成绩趋势图")
        self.setMinimumSize(800, 600)
        self.setModal(True)  # 设置为模态对话框
        self.scores_data = scores_data
        
        layout = QVBoxLayout(self)
        
        # 图表标签
        self.lbl_chart = QLabel("正在生成图表...")
        self.lbl_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart.setStyleSheet("font-size: 14px; padding: 20px;")
        layout.addWidget(self.lbl_chart)
        
        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        # 延迟生成图表，确保对话框先显示
        QTimer.singleShot(200, self.generate_chart_delayed)
    
    def closeEvent(self, event):
        """重写关闭事件，确保不影响父窗口"""
        # 只关闭对话框，不影响父窗口
        event.accept()
        # 尝试确保主窗口仍然可见（如果父对象存在）
        try:
            if self.parent():
                parent = self.parent()
                # 向上查找主窗口
                while parent and not hasattr(parent, 'setWindowTitle'):
                    parent = parent.parent()
                if parent:
                    try:
                        parent.show()
                        parent.raise_()
                        parent.activateWindow()
                    except:
                        pass
        except:
            pass
    
    def generate_chart_delayed(self):
        """延迟生成图表"""
        try:
            if not hasattr(self, 'lbl_chart'):
                return
            self.generate_chart(self.scores_data)
        except RuntimeError:
            # 对象已被删除，忽略
            pass
        except Exception as e:
            try:
                if hasattr(self, 'lbl_chart'):
                    self.lbl_chart.setText(f"生成图表失败：{str(e)}")
            except RuntimeError:
                pass
    
    def generate_chart(self, scores_data):
        """生成成绩趋势图"""
        try:
            # 先检查 matplotlib 是否可用
            try:
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                from io import BytesIO
            except ImportError:
                try:
                    self.lbl_chart.setText("需要安装 matplotlib 库才能显示图表\n请运行: pip install matplotlib")
                except RuntimeError:
                    pass
                return
            
            # 配置中文字体
            try:
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
            except:
                pass  # 如果配置失败，继续使用默认字体
            
            # 过滤有效成绩
            valid_scores = []
            course_names = []
            for s in scores_data:
                score = s.get("score")
                if score is not None:
                    try:
                        valid_scores.append(float(score))
                        course_names.append(s.get("course_name", ""))
                    except:
                        pass
            
            if not valid_scores:
                try:
                    self.lbl_chart.setText("暂无有效成绩数据")
                except RuntimeError:
                    pass
                return
            
            # 创建图表
            fig = None
            try:
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
                
                # 成绩趋势折线图
                ax1.plot(range(len(valid_scores)), valid_scores, marker='o', linewidth=2, markersize=8)
                ax1.set_xlabel('Course Number', fontsize=12)
                ax1.set_ylabel('Score', fontsize=12)
                ax1.set_title('Score Trend', fontsize=14, fontweight='bold')
                ax1.grid(True, alpha=0.3)
                ax1.set_ylim(0, 100)
                
                # 成绩分布柱状图
                grade_ranges = ['<60', '60-69', '70-79', '80-89', '≥90']
                grade_counts = [
                    sum(1 for s in valid_scores if s < 60),
                    sum(1 for s in valid_scores if 60 <= s < 70),
                    sum(1 for s in valid_scores if 70 <= s < 80),
                    sum(1 for s in valid_scores if 80 <= s < 90),
                    sum(1 for s in valid_scores if s >= 90)
                ]
                ax2.bar(grade_ranges, grade_counts, color=['#f44336', '#ff9800', '#ffeb3b', '#4caf50', '#2196f3'])
                ax2.set_xlabel('Score Range', fontsize=12)
                ax2.set_ylabel('Course Count', fontsize=12)
                ax2.set_title('Score Distribution', fontsize=14, fontweight='bold')
                ax2.grid(True, alpha=0.3, axis='y')
                
                plt.tight_layout()
                
                # 转换为图片
                buf = BytesIO()
                try:
                    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
                    buf.seek(0)
                    pixmap = QPixmap()
                    if pixmap.loadFromData(buf.read()):
                        try:
                            self.lbl_chart.setPixmap(pixmap)
                        except RuntimeError:
                            pass
                    else:
                        try:
                            self.lbl_chart.setText("图表生成失败：无法加载图片")
                        except RuntimeError:
                            pass
                finally:
                    buf.close()
            finally:
                if fig:
                    plt.close(fig)
                plt.close('all')  # 确保关闭所有图表
            
        except Exception as e:
            try:
                error_msg = f"生成图表失败：{str(e)}"
                self.lbl_chart.setText(error_msg)
            except RuntimeError:
                pass
            except Exception:
                # 如果连设置文本都失败，就忽略
                pass

class StudentMyGradesPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.all_scores = []  # 保存所有成绩数据
        self.student_id = None  # 保存 student_id

        layout = QVBoxLayout(self)

        title_layout = QHBoxLayout()
        title = QLabel("📝 我的成绩")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 筛选区域
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选："))
        
        # 课程名筛选
        filter_layout.addWidget(QLabel("课程名："))
        self.combo_course = QComboBox()
        self.combo_course.addItem("全部")
        self.combo_course.setMinimumWidth(150)
        self.combo_course.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.combo_course)
        
        # 学期筛选
        filter_layout.addWidget(QLabel("学期："))
        self.combo_semester = QComboBox()
        self.combo_semester.addItem("全部")
        self.combo_semester.setMinimumWidth(150)
        self.combo_semester.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.combo_semester)
        
        filter_layout.addStretch()
        
        # 按钮区域
        self.btn_export = QPushButton("导出CSV")
        self.btn_export.clicked.connect(self.export_to_csv)
        filter_layout.addWidget(self.btn_export)
        
        self.btn_chart = QPushButton("图表查看成绩趋势")
        self.btn_chart.clicked.connect(self.show_chart)
        filter_layout.addWidget(self.btn_chart)
        
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        filter_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(title_layout)
        layout.addLayout(filter_layout)

        # 统计信息区域（显示GPA和加权平均分）
        stats_layout = QHBoxLayout()
        self.lbl_stats = QLabel("正在加载统计信息...")
        self.lbl_stats.setTextFormat(Qt.TextFormat.RichText)  # 启用HTML格式
        self.lbl_stats.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                color: #1f1f1f;
            }
        """)
        stats_layout.addWidget(self.lbl_stats)
        layout.addLayout(stats_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "课程名", "成绩", "学期", "状态"]
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
        """刷新成绩列表"""
        if not self.student_id:
            self.init_student_info()
        
        if not self.student_id:
            try:
                QMessageBox.warning(self, "错误", "无法获取学生ID")
            except Exception:
                pass
            return

        try:
            resp = self.api.get("/api/scores", params={"student_id": str(self.student_id)})
            data = resp.json()
        except Exception as e:
            try:
                QMessageBox.critical(self, "错误", f"获取成绩失败：{e}")
            except Exception:
                pass
            return

        if data.get("status") != "ok":
            try:
                QMessageBox.warning(self, "错误", data.get("msg", "未知错误"))
            except Exception:
                pass
            return

        scores = data.get("data", [])
        self.all_scores = scores
        
        # 更新筛选下拉框
        self.update_filters(scores)
        
        # 应用筛选
        self.apply_filter()
    
    def update_filters(self, scores):
        """更新筛选下拉框选项"""
        # 获取所有课程名
        course_names = set()
        semesters = set()
        
        for s in scores:
            course_name = s.get("course_name", "")
            if course_name:
                course_names.add(course_name)
            
            # 从课程信息中获取学期
            # 如果没有学期信息，尝试从exam_date推断
            semester = s.get("semester", "")
            if not semester:
                exam_date = s.get("exam_date", "")
                if exam_date:
                    # 从日期推断学期（简单处理）
                    try:
                        year = exam_date[:4]
                        month = int(exam_date[5:7]) if len(exam_date) > 5 else 1
                        if 2 <= month <= 7:
                            semester = f"{year}春"
                        else:
                            semester = f"{year}秋"
                    except:
                        pass
            if semester:
                semesters.add(semester)
        
        # 更新课程名下拉框
        current_course = self.combo_course.currentText()
        self.combo_course.clear()
        self.combo_course.addItem("全部")
        for name in sorted(course_names):
            self.combo_course.addItem(name)
        if current_course in [self.combo_course.itemText(i) for i in range(self.combo_course.count())]:
            self.combo_course.setCurrentText(current_course)
        
        # 更新学期下拉框
        current_semester = self.combo_semester.currentText()
        self.combo_semester.clear()
        self.combo_semester.addItem("全部")
        for sem in sorted(semesters, reverse=True):
            self.combo_semester.addItem(sem)
        if current_semester in [self.combo_semester.itemText(i) for i in range(self.combo_semester.count())]:
            self.combo_semester.setCurrentText(current_semester)
    
    def apply_filter(self):
        """应用筛选条件"""
        course_filter = self.combo_course.currentText()
        semester_filter = self.combo_semester.currentText()
        
        # 筛选数据
        filtered_scores = []
        for s in self.all_scores:
            # 课程名筛选
            if course_filter != "全部":
                if s.get("course_name", "") != course_filter:
                    continue
            
            # 学期筛选
            if semester_filter != "全部":
                semester = s.get("semester", "")
                if not semester:
                    exam_date = s.get("exam_date", "")
                    if exam_date:
                        try:
                            year = exam_date[:4]
                            month = int(exam_date[5:7]) if len(exam_date) > 5 else 1
                            if 2 <= month <= 7:
                                semester = f"{year}春"
                            else:
                                semester = f"{year}秋"
                        except:
                            pass
                if semester != semester_filter:
                    continue
            
            filtered_scores.append(s)
        
        # 显示筛选后的数据
        self.display_scores(filtered_scores)
        # 更新统计信息
        self.update_stats(filtered_scores)
    
    def display_scores(self, scores):
        """显示成绩列表"""
        self.table.setRowCount(len(scores))
        for i, s in enumerate(scores):
            score_value = s.get("score")
            status = ""
            if score_value is not None:
                score_float = float(score_value)
                if score_float >= 90:
                    status = "优秀"
                elif score_float >= 80:
                    status = "良好"
                elif score_float >= 70:
                    status = "中等"
                elif score_float >= 60:
                    status = "及格"
                else:
                    status = "不及格"
            else:
                status = "未评分"
            
            # 获取学期信息
            semester = s.get("semester", "")
            if not semester:
                exam_date = s.get("exam_date", "")
                if exam_date:
                    try:
                        year = exam_date[:4]
                        month = int(exam_date[5:7]) if len(exam_date) > 5 else 1
                        if 2 <= month <= 7:
                            semester = f"{year}春"
                        else:
                            semester = f"{year}秋"
                    except:
                        semester = exam_date[:7] if exam_date else "未知"
                else:
                    semester = "未知"

            items = [
                QTableWidgetItem(str(s.get("score_id", ""))),
                QTableWidgetItem(s.get("course_name", "")),
                QTableWidgetItem(str(score_value) if score_value is not None else "未评分"),
                QTableWidgetItem(semester),
                QTableWidgetItem(status),
            ]
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor("#1f1f1f"))

            for col_idx, item in enumerate(items):
                self.table.setItem(i, col_idx, item)
    
    def score_to_gpa(self, score):
        """将百分制成绩转换为GPA（0-4体系）"""
        if score is None:
            return None
        try:
            score = float(score)
            if score >= 90:
                return 4.0
            elif score >= 85:
                return 3.7
            elif score >= 82:
                return 3.3
            elif score >= 78:
                return 3.0
            elif score >= 75:
                return 2.7
            elif score >= 72:
                return 2.3
            elif score >= 68:
                return 2.0
            elif score >= 66:
                return 1.7
            elif score >= 64:
                return 1.5
            elif score >= 60:
                return 1.0
            else:
                return 0.0
        except (ValueError, TypeError):
            return None
    
    def calculate_gpa_and_weighted_avg(self, courses_data):
        """计算GPA和加权平均分"""
        if not courses_data:
            return None, None, 0
        
        # 计算加权平均分
        total_weighted_score = sum(c["score"] * c["credit"] for c in courses_data)
        total_credits = sum(c["credit"] for c in courses_data)
        weighted_avg = total_weighted_score / total_credits if total_credits > 0 else 0
        
        # 计算GPA
        total_gpa_points = 0
        for c in courses_data:
            gpa_point = self.score_to_gpa(c["score"])
            if gpa_point is not None:
                total_gpa_points += gpa_point * c["credit"]
        
        gpa = total_gpa_points / total_credits if total_credits > 0 else 0
        
        return round(gpa, 2), round(weighted_avg, 2), total_credits
    
    def update_stats(self, scores):
        """更新统计信息显示（GPA和加权平均分）"""
        try:
            # 收集有效课程数据（有成绩和学分的）
            valid_courses_data = []
            valid_scores = []
            
            for s in scores:
                score = s.get("score")
                credit = s.get("credit")
                
                if score is not None:
                    try:
                        score_val = float(score)
                        if 0 <= score_val <= 100:
                            valid_scores.append(score_val)
                            # 如果有学分信息，添加到有效课程数据中
                            if credit is not None:
                                try:
                                    credit_val = float(credit)
                                    if credit_val > 0:
                                        valid_courses_data.append({
                                            "score": score_val,
                                            "credit": credit_val
                                        })
                                except (ValueError, TypeError):
                                    pass
                    except (ValueError, TypeError):
                        pass
            
            if not valid_scores:
                self.lbl_stats.setText("暂无有效成绩数据")
                return
            
            # 计算统计数据
            total = len(valid_scores)
            avg_score = sum(valid_scores) / total if total > 0 else 0
            
            # 计算GPA和加权平均分
            gpa, weighted_avg, total_credits = self.calculate_gpa_and_weighted_avg(valid_courses_data)
            
            # 生成统计文本
            stats_text = f"📊 统计信息：总课程数 {total} 门 | 平均分 {avg_score:.2f} 分"
            
            if weighted_avg is not None and total_credits > 0:
                stats_text += f" | 加权平均分 <span style='color: #4CAF50; font-weight: bold;'>{weighted_avg:.2f}</span> 分（总学分：{total_credits:.1f}）"
                stats_text += f" | GPA <span style='color: #2196F3; font-weight: bold; font-size: 16px;'>{gpa:.2f}</span> / 4.0"
            
            self.lbl_stats.setText(stats_text)
        except Exception as e:
            self.lbl_stats.setText(f"计算统计信息失败：{str(e)}")
    
    def export_to_csv(self):
        """导出成绩为CSV"""
        if not self.all_scores:
            try:
                QMessageBox.warning(self, "提示", "没有可导出的成绩数据")
            except Exception:
                pass
            return
        
        # 获取保存文件路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出CSV", "成绩单.csv", "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(["ID", "课程名", "成绩", "学期", "状态", "考试日期"])
                
                # 写入数据
                for s in self.all_scores:
                    score_value = s.get("score")
                    status = ""
                    if score_value is not None:
                        score_float = float(score_value)
                        if score_float >= 90:
                            status = "优秀"
                        elif score_float >= 80:
                            status = "良好"
                        elif score_float >= 70:
                            status = "中等"
                        elif score_float >= 60:
                            status = "及格"
                        else:
                            status = "不及格"
                    else:
                        status = "未评分"
                    
                    semester = s.get("semester", "")
                    if not semester:
                        exam_date = s.get("exam_date", "")
                        if exam_date:
                            try:
                                year = exam_date[:4]
                                month = int(exam_date[5:7]) if len(exam_date) > 5 else 1
                                if 2 <= month <= 7:
                                    semester = f"{year}春"
                                else:
                                    semester = f"{year}秋"
                            except:
                                semester = exam_date[:7] if exam_date else "未知"
                        else:
                            semester = "未知"
                    
                    writer.writerow([
                        s.get("score_id", ""),
                        s.get("course_name", ""),
                        str(score_value) if score_value is not None else "未评分",
                        semester,
                        status,
                        s.get("exam_date", "")
                    ])
            
            try:
                msg_box = QMessageBox()
                msg_box.setWindowTitle("成功")
                msg_box.setText(f"成绩已成功导出到：\n{file_path}")
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()
            except Exception:
                pass
        except Exception as e:
            try:
                QMessageBox.critical(self, "错误", f"导出失败：{str(e)}")
            except Exception:
                pass
    
    def show_chart(self):
        """显示成绩趋势图表"""
        if not self.all_scores:
            try:
                # 获取主窗口作为父对象
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                parent = app.activeWindow() if app else None
                msg_box = QMessageBox(parent)
                msg_box.setWindowTitle("提示")
                msg_box.setText("没有可显示的成绩数据")
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()
            except Exception:
                pass
            return
        
        dialog = None
        try:
            # 获取主窗口作为父对象，而不是使用 self
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            parent_window = app.activeWindow() if app else None
            
            # 如果无法获取主窗口，使用 None（独立窗口）
            dialog = GradeChartDialog(parent_window, self.all_scores)
            # 使用 exec() 显示模态对话框
            dialog.exec()
        except RuntimeError as e:
            # 对象已被删除，尝试使用独立窗口
            try:
                dialog = GradeChartDialog(None, self.all_scores)
                dialog.exec()
            except Exception as e2:
                print(f"对话框错误（已忽略）：{e}, {e2}")
        except Exception as e:
            print(f"显示图表失败：{e}")
            import traceback
            traceback.print_exc()
            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                parent = app.activeWindow() if app else None
                msg_box = QMessageBox(parent)
                msg_box.setWindowTitle("错误")
                msg_box.setText(f"显示图表失败：{str(e)}")
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()
            except Exception:
                pass
        finally:
            # 清理对话框引用
            if dialog:
                try:
                    dialog.deleteLater()
                except:
                    pass

