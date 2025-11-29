# client/pages/student_my_grades_page.py
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHBoxLayout, QLabel, QComboBox,
    QFileDialog, QDialog, QHeaderView, QApplication, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPixmap
from ..utils.api_client import APIClient
import requests

class GradeChartDialog(QDialog):
    """成绩趋势/分布图表对话框"""
    def __init__(self, parent, scores_data):
        super().__init__(parent)
        self.setWindowTitle("成绩图表")
        
        # 获取屏幕尺寸并设置窗口大小
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                screen_geometry = screen.geometry()
                screen_width = screen_geometry.width()
                screen_height = screen_geometry.height()
                # 宽度：半个屏幕，高度：整个屏幕
                dialog_width = screen_width // 2
                dialog_height = screen_height
                self.resize(dialog_width, dialog_height)
                self.setMinimumSize(dialog_width, dialog_height)
            else:
                # 如果无法获取屏幕尺寸，使用默认值
                self.setMinimumSize(800, 600)
                self.resize(800, 600)
        else:
            # 如果无法获取应用实例，使用默认值
            self.setMinimumSize(800, 600)
            self.resize(800, 600)
        
        self.setModal(True)  # 设置为模态对话框
        self.scores_data = scores_data
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 导航栏区域
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(5)
        nav_layout.setContentsMargins(0, 0, 0, 10)
        
        self.chart_modes = [
            ("trend", "📈 成绩趋势"),
            ("distribution", "📊 成绩分布"),
            ("pie", "🥧 成绩区间"),
            ("semester", "🗓 学期平均分"),
        ]
        
        # 创建按钮组
        self.chart_button_group = QButtonGroup(self)
        self.chart_buttons = []
        self.current_chart_type = "trend"  # 默认选中第一个
        
        for i, (key, label) in enumerate(self.chart_modes):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # 设置按钮样式
            if i == 0:
                # 第一个按钮默认选中
                btn.setChecked(True)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #1976D2;
                    }
                    QPushButton:pressed {
                        background-color: #0D47A1;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f5f5f5;
                        color: #333;
                        border: 1px solid #ddd;
                        padding: 10px 20px;
                        border-radius: 6px;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                        border-color: #bbb;
                    }
                    QPushButton:checked {
                        background-color: #2196F3;
                        color: white;
                        border: none;
                        font-weight: bold;
                    }
                """)
            
            btn.clicked.connect(lambda checked, k=key: self.on_chart_type_changed(k))
            self.chart_button_group.addButton(btn, i)
            self.chart_buttons.append(btn)
            nav_layout.addWidget(btn)
        
        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        # 图表标签
        self.lbl_chart = QLabel("正在生成图表...")
        self.lbl_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
                padding: 20px;
            }
        """)
        self.lbl_chart.setScaledContents(False)
        layout.addWidget(self.lbl_chart, 1)
        self.current_pixmap = None
        
        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        # 延迟生成图表，确保对话框先显示
        QTimer.singleShot(200, self.generate_chart_delayed)
    
    def on_chart_type_changed(self, chart_type):
        """图表类型切换回调"""
        self.current_chart_type = chart_type
        # 更新按钮样式
        for i, (key, _) in enumerate(self.chart_modes):
            btn = self.chart_buttons[i]
            if key == chart_type:
                btn.setChecked(True)
            else:
                btn.setChecked(False)
        # 重新生成图表
        self.generate_chart_delayed()
    
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
            chart_type = getattr(self, 'current_chart_type', 'trend')
            self.generate_chart(self.scores_data, chart_type)
        except RuntimeError:
            pass
        except Exception as e:
            try:
                if hasattr(self, 'lbl_chart'):
                    self.lbl_chart.setText(f"生成图表失败：{str(e)}")
            except RuntimeError:
                pass
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pixmap_display()

    def update_pixmap_display(self):
        """根据标签大小自适应显示图片"""
        if self.current_pixmap and not self.current_pixmap.isNull():
            scaled = self.current_pixmap.scaled(
                self.lbl_chart.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_chart.setPixmap(scaled)

    def _prepare_valid_data(self, scores_data):
        """过滤有效成绩数据"""
        valid_data = []
        for s in scores_data:
            score = s.get("score")
            if score is None:
                continue
            try:
                score_val = float(score)
            except (ValueError, TypeError):
                continue
            entry = {
                "score": score_val,
                "course_name": s.get("course_name", "未知课程"),
                "semester": s.get("semester", ""),
                "exam_date": s.get("exam_date", "")
            }
            valid_data.append(entry)
        return valid_data

    def generate_chart(self, scores_data, chart_type="trend"):
        """生成图表"""
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
            
            valid_data = self._prepare_valid_data(scores_data)
            if not valid_data:
                self.lbl_chart.setText("暂无有效成绩数据")
                self.current_pixmap = None
                return
            
            fig = None
            try:
                if chart_type == "distribution":
                    fig = self._plot_distribution_bar(valid_data)
                elif chart_type == "pie":
                    fig = self._plot_distribution_pie(valid_data)
                elif chart_type == "semester":
                    fig = self._plot_semester_trend(valid_data)
                else:
                    fig = self._plot_score_trend(valid_data)

                if fig is None:
                    return

                buf = BytesIO()
                try:
                    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
                    buf.seek(0)
                    pixmap = QPixmap()
                    if pixmap.loadFromData(buf.read()):
                        self.current_pixmap = pixmap
                        self.lbl_chart.setText("")
                        self.update_pixmap_display()
                    else:
                        self.current_pixmap = None
                        self.lbl_chart.setPixmap(QPixmap())
                        self.lbl_chart.setText("图表生成失败：无法加载图片")
                finally:
                    buf.close()
            finally:
                if fig:
                    plt.close(fig)
                plt.close('all')
            
        except Exception as e:
            self.current_pixmap = None
            try:
                self.lbl_chart.setText(f"生成图表失败：{str(e)}")
            except RuntimeError:
                pass

    def _plot_score_trend(self, data):
        """成绩趋势折线图"""
        import matplotlib.pyplot as plt
        if not data:
            self.lbl_chart.setText("暂无成绩数据")
            return None
        # 按考试日期排序
        sorted_data = sorted(
            data,
            key=lambda x: (x.get("exam_date") or "", x.get("course_name"))
        )
        scores = [d["score"] for d in sorted_data]
        labels = [d["course_name"] for d in sorted_data]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(range(len(scores)), scores, marker='o', linewidth=2, color='#2196F3')
        ax.fill_between(range(len(scores)), scores, alpha=0.1, color='#64B5F6')
        ax.set_xticks(range(len(scores)))
        ax.set_xticklabels([label[:12] + "..." if len(label) > 12 else label for label in labels],
                           rotation=45, ha='right', fontsize=9)
        ax.set_ylim(0, 105)
        ax.set_ylabel('成绩', fontsize=12)
        ax.set_title('成绩趋势（按考试时间顺序）', fontsize=14, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.3)
        return fig

    def _plot_distribution_bar(self, data):
        import matplotlib.pyplot as plt
        scores = [d["score"] for d in data]
        grade_ranges = ['<60', '60-69', '70-79', '80-89', '≥90']
        grade_counts = [
            sum(1 for s in scores if s < 60),
            sum(1 for s in scores if 60 <= s < 70),
            sum(1 for s in scores if 70 <= s < 80),
            sum(1 for s in scores if 80 <= s < 90),
            sum(1 for s in scores if s >= 90)
        ]
        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.bar(grade_ranges, grade_counts, color=['#f44336', '#ff9800', '#ffeb3b', '#4caf50', '#2196f3'])
        ax.set_xlabel('成绩区间', fontsize=12)
        ax.set_ylabel('课程数量', fontsize=12)
        ax.set_title('成绩分布（柱状图）', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        for bar, count in zip(bars, grade_counts):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    str(count), ha='center', va='bottom', fontsize=10, fontweight='bold')
        return fig

    def _plot_distribution_pie(self, data):
        import matplotlib.pyplot as plt
        scores = [d["score"] for d in data]
        sections = [
            ('优秀 ≥90', sum(1 for s in scores if s >= 90), '#4caf50'),
            ('良好 80-89', sum(1 for s in scores if 80 <= s < 90), '#8bc34a'),
            ('中等 70-79', sum(1 for s in scores if 70 <= s < 80), '#ffc107'),
            ('及格 60-69', sum(1 for s in scores if 60 <= s < 70), '#ff9800'),
            ('不及格 <60', sum(1 for s in scores if s < 60), '#f44336'),
        ]
        filtered = [sec for sec in sections if sec[1] > 0]
        if not filtered:
            self.lbl_chart.setText("暂无成绩区间数据")
            return None
        labels, counts, colors = zip(*filtered)
        fig, ax = plt.subplots(figsize=(7, 7))
        wedges, texts, autotexts = ax.pie(
            counts,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            explode=[0.03] * len(counts),
            textprops={'fontsize': 10}
        )
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        ax.set_title('成绩区间占比（饼图）', fontsize=14, fontweight='bold')
        return fig

    def _plot_semester_trend(self, data):
        import matplotlib.pyplot as plt
        from collections import defaultdict
        semester_scores = defaultdict(list)
        for d in data:
            sem = d.get("semester") or self._infer_semester(d.get("exam_date"))
            if sem:
                semester_scores[sem].append(d["score"])
        if not semester_scores:
            self.lbl_chart.setText("暂无学期数据")
            return None
        semesters = sorted(semester_scores.keys())
        avg_scores = [sum(semester_scores[sem]) / len(semester_scores[sem]) for sem in semesters]
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(semesters, avg_scores, marker='o', linewidth=2.5, color='#673ab7')
        ax.fill_between(semesters, avg_scores, alpha=0.15, color='#9575cd')
        ax.set_ylim(0, 105)
        ax.set_xlabel('学期', fontsize=12)
        ax.set_ylabel('平均分', fontsize=12)
        ax.set_title('各学期平均成绩', fontsize=14, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.3)
        for sem, score in zip(semesters, avg_scores):
            ax.text(sem, score + 1.5, f"{score:.1f}", ha='center', fontsize=10, fontweight='bold')
        plt.xticks(rotation=30)
        return fig

    def _infer_semester(self, exam_date):
        if not exam_date:
            return ""
        try:
            year = exam_date[:4]
            month = int(exam_date[5:7]) if len(exam_date) > 5 else 1
            if 2 <= month <= 7:
                return f"{year}春"
            return f"{year}秋"
        except Exception:
            return ""

class StudentMyGradesPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.all_scores = []  # 保存所有成绩数据
        self.filtered_scores = []  # 保存当前筛选结果
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
        # 保存当前筛选结果
        self.filtered_scores = filtered_scores
    
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
        scores_source = self.filtered_scores if self.filtered_scores else self.all_scores
        if not scores_source:
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
            dialog = GradeChartDialog(parent_window, scores_source)
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

