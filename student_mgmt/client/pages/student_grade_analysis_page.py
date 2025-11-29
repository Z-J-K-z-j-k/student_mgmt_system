# client/pages/student_grade_analysis_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QScrollArea, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from ..utils.api_client import APIClient


class StudentGradeAnalysisPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
        self.student_id = None  # 保存 student_id
        self.scores_data = []
        self._is_destroyed = False  # 标记对象是否已被销毁

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 标题
        title = QLabel("📊 成绩分析")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        main_layout.addWidget(title)

        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # 统计信息显示
        self.lbl_stats = QLabel("正在加载数据...")
        self.lbl_stats.setTextFormat(Qt.TextFormat.RichText)  # 启用HTML格式
        self.lbl_stats.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
                font-size: 14px;
                color: #1f1f1f;
                min-height: 100px;
            }
        """)
        self.lbl_stats.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_stats.setWordWrap(True)
        content_layout.addWidget(self.lbl_stats)

        # 图表展示区域
        charts_title = QLabel("📈 图表分析")
        charts_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; margin-top: 10px;")
        content_layout.addWidget(charts_title)

        # 图表导航栏（位于图表上方）
        self.chart_modes = [
            ("bar", "📊 每门课成绩"),
            ("pie", "🥧 成绩分布"),
            ("line", "📉 学期趋势"),
            ("hist", "📈 分数直方图"),
            ("scatter", "🔹 成绩散点"),
            ("box", "📦 成绩箱线图"),
            ("cum", "🧮 累计平均"),
        ]
        self.current_chart_type = self.chart_modes[0][0]
        self.chart_button_group = QButtonGroup(self)
        self.chart_button_group.setExclusive(True)
        self.chart_buttons = []

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        nav_layout.setContentsMargins(0, 10, 0, 10)

        for idx, (key, label) in enumerate(self.chart_modes):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    color: #333;
                    border: 1px solid #dcdcdc;
                    padding: 10px 16px;
                    border-radius: 8px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #e8f0fe;
                    border-color: #b0c4ff;
                }
                QPushButton:checked {
                    background-color: #1A73E8;
                    border-color: #1A73E8;
                    color: white;
                    font-weight: bold;
                }
            """)
            btn.setChecked(idx == 0)
            btn.clicked.connect(lambda checked, chart_key=key: self.on_chart_type_changed(chart_key))
            self.chart_button_group.addButton(btn, idx)
            self.chart_buttons.append(btn)
            nav_layout.addWidget(btn)

        nav_layout.addStretch()
        content_layout.addLayout(nav_layout)

        self.chart_display = QLabel("等待数据加载...")
        self.chart_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_display.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                min-height: 420px;
                padding: 24px;
                font-size: 14px;
                color: #666;
            }
        """)
        self.chart_display.setScaledContents(False)
        self.chart_pixmap = None
        content_layout.addWidget(self.chart_display)
        content_layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 刷新分析")
        self.btn_refresh.setStyleSheet("""
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
        self.btn_refresh.clicked.connect(self.refresh)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # 初始化：获取 student_id
        self.init_student_info()
        # 延迟刷新，确保窗口完全初始化后再加载数据
        QTimer.singleShot(500, self.refresh)

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

    def is_valid(self):
        """检查对象是否仍然有效"""
        return not self._is_destroyed and hasattr(self, 'lbl_stats')

    def safe_set_label_text(self, label_name, text):
        """安全地设置标签文本"""
        if not self.is_valid():
            return
        try:
            label = getattr(self, label_name, None)
            if label is not None:
                label.setText(str(text))
        except (RuntimeError, AttributeError):
            pass

    def on_chart_type_changed(self, chart_type: str):
        """切换图表类型"""
        self.current_chart_type = chart_type
        self.render_selected_chart()

    def refresh(self):
        """刷新成绩分析"""
        if not self.is_valid():
            return

        try:
            # 检查 API 客户端
            if not self.api or not hasattr(self.api, 'get'):
                self.safe_set_label_text("lbl_stats", "API 客户端未初始化")
                self.clear_charts()
                return

            # 显示加载状态
            self.safe_set_label_text("lbl_stats", "正在加载成绩数据...")
            if hasattr(self, "chart_display"):
                self.chart_display.setText("正在生成图表，请稍候...")
                self.chart_display.setPixmap(QPixmap())
                self.chart_pixmap = None

            # 确保已获取 student_id
            if not self.student_id:
                self.init_student_info()
            
            if not self.student_id:
                self.safe_set_label_text("lbl_stats", "无法获取学生ID，请检查登录状态")
                self.clear_charts()
                return
            
            # 调用 API
            resp = self.api.get("/api/scores", params={"student_id": str(self.student_id)})
            
            # 检查响应状态码
            if resp.status_code != 200:
                self.safe_set_label_text("lbl_stats", f"服务器错误：{resp.status_code}")
                self.clear_charts()
                return

            # 解析 JSON
            try:
                data = resp.json()
            except (ValueError, AttributeError) as e:
                self.safe_set_label_text("lbl_stats", f"响应解析失败：{str(e)}")
                self.clear_charts()
                return

            # 检查响应格式
            if not isinstance(data, dict) or data.get("status") != "ok":
                error_msg = data.get("msg", "未知错误") if isinstance(data, dict) else "响应格式错误"
                self.safe_set_label_text("lbl_stats", f"错误：{error_msg}")
                self.clear_charts()
                return

            scores = data.get("data", [])
            if not isinstance(scores, list):
                self.safe_set_label_text("lbl_stats", "数据格式错误：成绩列表不是数组")
                self.clear_charts()
                return

            self.scores_data = scores
            
            if not scores:
                self.safe_set_label_text("lbl_stats", "暂无成绩数据")
                self.clear_charts()
                return

            # 计算统计信息
            self.calculate_and_display_stats(scores)
            
            # 延迟生成图表，确保界面先更新
            QTimer.singleShot(300, self.render_selected_chart)

        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg or "timeout" in error_msg.lower():
                self.safe_set_label_text("lbl_stats", "无法连接到服务器，请检查服务器是否运行")
            else:
                self.safe_set_label_text("lbl_stats", f"获取成绩失败：{error_msg}")
            self.clear_charts()

    def calculate_and_display_stats(self, scores):
        """计算并显示统计信息"""
        if not self.is_valid():
            return

        try:
            # 过滤有效成绩
            valid_scores = []
            valid_courses_data = []  # 用于计算GPA和加权平均分
            for s in scores:
                if not isinstance(s, dict):
                    continue
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
                self.safe_set_label_text("lbl_stats", "暂无有效成绩数据")
                return

            # 计算统计数据
            total = len(valid_scores)
            avg_score = sum(valid_scores) / total
            max_score = max(valid_scores)
            min_score = min(valid_scores)

            # 统计各等级数量
            excellent = sum(1 for s in valid_scores if s >= 90)
            good = sum(1 for s in valid_scores if 80 <= s < 90)
            medium = sum(1 for s in valid_scores if 70 <= s < 80)
            pass_count = sum(1 for s in valid_scores if 60 <= s < 70)
            fail = sum(1 for s in valid_scores if s < 60)

            # 计算GPA和加权平均分
            gpa, weighted_avg, total_credits = self.calculate_gpa_and_weighted_avg(valid_courses_data)

            # 生成统计文本
            stats_text = f"""
            <h3 style="color: #2196F3; margin-top: 0;">成绩统计概览</h3>
            <p><b>总课程数：</b>{total} 门</p>
            <p><b>平均分：</b><span style="color: #4CAF50; font-weight: bold;">{avg_score:.2f}</span> 分</p>
            """
            
            # 如果有学分信息，显示加权平均分和GPA
            if weighted_avg is not None and total_credits > 0:
                stats_text += f"""
            <p><b>加权平均分：</b><span style="color: #4CAF50; font-weight: bold;">{weighted_avg:.2f}</span> 分（总学分：{total_credits:.1f}）</p>
            <p><b>GPA：</b><span style="color: #2196F3; font-weight: bold; font-size: 16px;">{gpa:.2f}</span> / 4.0</p>
            """
            
            stats_text += f"""
            <p><b>最高分：</b><span style="color: #2196F3;">{max_score}</span> 分</p>
            <p><b>最低分：</b><span style="color: #FF9800;">{min_score}</span> 分</p>
            <hr style="border: 1px solid #e0e0e0;">
            <h4 style="color: #666;">成绩分布</h4>
            <p><b>优秀（≥90分）：</b><span style="color: #4CAF50;">{excellent}</span> 门 ({excellent/total*100:.1f}%)</p>
            <p><b>良好（80-89分）：</b><span style="color: #8BC34A;">{good}</span> 门 ({good/total*100:.1f}%)</p>
            <p><b>中等（70-79分）：</b><span style="color: #FFC107;">{medium}</span> 门 ({medium/total*100:.1f}%)</p>
            <p><b>及格（60-69分）：</b><span style="color: #FF9800;">{pass_count}</span> 门 ({pass_count/total*100:.1f}%)</p>
            <p><b>不及格（<60分）：</b><span style="color: #F44336;">{fail}</span> 门 ({fail/total*100:.1f}%)</p>
            <hr style="border: 1px solid #e0e0e0;">
            <p><b>及格率：</b><span style="color: #4CAF50; font-weight: bold;">{(total-fail)/total*100:.1f}%</span></p>
            <p><b>优秀率：</b><span style="color: #2196F3; font-weight: bold;">{excellent/total*100:.1f}%</span></p>
            """
            self.safe_set_label_text("lbl_stats", stats_text)

        except Exception as e:
            self.safe_set_label_text("lbl_stats", f"计算统计信息失败：{str(e)}")
    
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

    def clear_charts(self):
        """清空图表"""
        self.chart_pixmap = None
        if hasattr(self, "chart_display"):
            try:
                self.chart_display.clear()
                self.chart_display.setText("暂无图表数据")
            except Exception:
                pass

    def render_selected_chart(self):
        """根据当前选择生成图表"""
        self.generate_chart(getattr(self, "current_chart_type", "bar"))

    def generate_chart(self, chart_type: str):
        """生成指定类型的图表"""
        if not self.is_valid():
            return

        if not getattr(self, "scores_data", None):
            self.chart_display.setText("暂无成绩数据")
            self.chart_pixmap = None
            return

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from io import BytesIO
        except ImportError:
            self.chart_display.setText("需要安装 matplotlib 库才能生成图表\n请运行: pip install matplotlib")
            return

        # 配置中文字体
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans', 'Arial']
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            pass

        valid_data = self._prepare_chart_data()
        if not valid_data:
            self.chart_display.setText("暂无有效成绩数据")
            self.chart_pixmap = None
            return

        chart_map = {
            "bar": self._plot_course_bar_chart,
            "pie": self._plot_grade_pie_chart,
            "line": self._plot_semester_line_chart,
            "hist": self._plot_histogram_chart,
            "scatter": self._plot_scatter_chart,
            "box": self._plot_box_chart,
            "cum": self._plot_cumulative_chart,
        }
        plot_func = chart_map.get(chart_type, self._plot_course_bar_chart)

        fig = plot_func(valid_data, plt)
        if fig is None:
            return

        try:
            from io import BytesIO
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            pixmap = QPixmap()
            if pixmap.loadFromData(buf.read()):
                self.chart_pixmap = pixmap
                self._update_chart_pixmap()
                self.chart_display.setText("")
            else:
                self.chart_display.setText("图表生成失败，无法加载图片数据")
                self.chart_pixmap = None
            buf.close()
        finally:
            plt.close(fig)
            plt.close('all')

    def _prepare_chart_data(self):
        """整理图表所需数据"""
        data = []
        for s in self.scores_data:
            if not isinstance(s, dict):
                continue
            score = s.get("score")
            if score is None:
                continue
            try:
                score_val = float(score)
            except (ValueError, TypeError):
                continue
            if not (0 <= score_val <= 100):
                continue
            data.append({
                "course_name": s.get("course_name", "未知课程"),
                "score": score_val,
                "semester": s.get("semester"),
                "credit": s.get("credit"),
                "exam_date": s.get("exam_date")
            })
        return data

    def _update_chart_pixmap(self):
        """自适应绘制当前图表"""
        if not hasattr(self, "chart_display"):
            return
        if self.chart_pixmap and not self.chart_pixmap.isNull():
            scaled = self.chart_pixmap.scaled(
                self.chart_display.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.chart_display.setPixmap(scaled)
        else:
            self.chart_display.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_chart_pixmap()

    def _plot_course_bar_chart(self, data, plt):
        if not data:
            self.chart_display.setText("暂无课程成绩数据")
            return None
        sorted_data = sorted(data, key=lambda x: x["score"], reverse=True)
        course_names = [d["course_name"] for d in sorted_data][:20]
        scores = [d["score"] for d in sorted_data][:20]
        labels = [name[:12] + "..." if len(name) > 12 else name for name in course_names]
        fig, ax = plt.subplots(figsize=(12, 5))
        bars = ax.bar(range(len(scores)), scores, color='#4CAF50', edgecolor='#2E7D32')
        ax.set_xticks(range(len(scores)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        ax.set_ylabel('成绩', fontsize=12)
        ax.set_ylim(0, 105)
        ax.set_title('每门课成绩（Top 20）', fontsize=14, fontweight='bold')
        ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        for bar, val in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width()/2, val + 1, f"{val:.1f}", ha='center', fontsize=9, fontweight='bold')
        plt.tight_layout()
        return fig

    def _plot_grade_pie_chart(self, data, plt):
        scores = [d["score"] for d in data]
        sections = [
            ('优秀 ≥90', sum(1 for s in scores if s >= 90), '#4CAF50'),
            ('良好 80-89', sum(1 for s in scores if 80 <= s < 90), '#8BC34A'),
            ('中等 70-79', sum(1 for s in scores if 70 <= s < 80), '#FFC107'),
            ('及格 60-69', sum(1 for s in scores if 60 <= s < 70), '#FF9800'),
            ('不及格 <60', sum(1 for s in scores if s < 60), '#F44336'),
        ]
        sections = [sec for sec in sections if sec[1] > 0]
        if not sections:
            self.chart_display.setText("暂无成绩区间数据")
            return None
        labels, counts, colors = zip(*sections)
        fig, ax = plt.subplots(figsize=(7, 7))
        wedges, texts, autotexts = ax.pie(
            counts,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            explode=[0.04] * len(counts),
            textprops={'fontsize': 10}
        )
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        ax.set_title('成绩等级占比', fontsize=14, fontweight='bold')
        return fig

    def _plot_semester_line_chart(self, data, plt):
        from collections import defaultdict
        semester_scores = defaultdict(list)
        for item in data:
            semester = item.get("semester") or self._infer_semester(item.get("exam_date"))
            if semester:
                semester_scores[semester].append(item["score"])
        if not semester_scores:
            self.chart_display.setText("暂无学期信息")
            return None
        semesters = sorted(semester_scores.keys())
        avg_scores = [sum(semester_scores[sem]) / len(semester_scores[sem]) for sem in semesters]
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(semesters, avg_scores, marker='o', linewidth=2.5, color='#2196F3')
        ax.fill_between(semesters, avg_scores, alpha=0.15, color='#64B5F6')
        ax.set_ylim(0, 105)
        ax.set_xlabel('学期', fontsize=12)
        ax.set_ylabel('平均成绩', fontsize=12)
        ax.set_title('学期平均成绩趋势', fontsize=14, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.3)
        for sem, score in zip(semesters, avg_scores):
            ax.text(sem, score + 1.5, f"{score:.1f}", ha='center', fontsize=10, fontweight='bold')
        plt.xticks(rotation=30)
        plt.tight_layout()
        return fig

    def _plot_histogram_chart(self, data, plt):
        scores = [d["score"] for d in data]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(scores, bins=10, range=(0, 100), color='#42A5F5', edgecolor='#1E88E5', alpha=0.9)
        ax.set_xlabel('分数区间', fontsize=12)
        ax.set_ylabel('课程数量', fontsize=12)
        ax.set_title('成绩直方图', fontsize=14, fontweight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()
        return fig

    def _plot_scatter_chart(self, data, plt):
        sorted_data = sorted(data, key=lambda x: (x.get("exam_date") or "", x["course_name"]))
        scores = [d["score"] for d in sorted_data]
        labels = [d["course_name"] for d in sorted_data]
        x = list(range(len(scores)))
        fig, ax = plt.subplots(figsize=(11, 5))
        scatter = ax.scatter(x, scores, c=scores, cmap='viridis', s=60, edgecolors='white', linewidths=0.8)
        ax.set_ylim(0, 105)
        ax.set_xticks(x)
        truncated_labels = [label[:10] + "..." if len(label) > 10 else label for label in labels]
        ax.set_xticklabels(truncated_labels, rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('成绩', fontsize=12)
        ax.set_title('成绩散点图（按时间顺序）', fontsize=14, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.3)
        fig.colorbar(scatter, ax=ax, label='成绩')
        plt.tight_layout()
        return fig

    def _plot_box_chart(self, data, plt):
        scores = [d["score"] for d in data]
        if len(scores) < 5:
            self.chart_display.setText("数据量不足，无法生成箱线图（至少需要5条记录）")
            return None
        fig, ax = plt.subplots(figsize=(6, 5))
        box = ax.boxplot(scores, vert=True, patch_artist=True,
                         boxprops=dict(facecolor='#90CAF9', color='#1E88E5'),
                         medianprops=dict(color='#E53935', linewidth=2),
                         whiskerprops=dict(color='#1E88E5'),
                         capprops=dict(color='#1E88E5'))
        ax.set_ylabel('成绩', fontsize=12)
        ax.set_title('成绩箱线图', fontsize=14, fontweight='bold')
        ax.set_xticks([])
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()
        return fig

    def _plot_cumulative_chart(self, data, plt):
        sorted_data = sorted(data, key=lambda x: (x.get("exam_date") or "", x["course_name"]))
        scores = [d["score"] for d in sorted_data]
        cumulative = []
        total = 0
        for idx, score in enumerate(scores, start=1):
            total += score
            cumulative.append(total / idx)
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(range(1, len(cumulative) + 1), cumulative, marker='o', color='#FF7043', linewidth=2.5)
        ax.set_ylim(0, 105)
        ax.set_xlabel('课程数量', fontsize=12)
        ax.set_ylabel('累计平均分', fontsize=12)
        ax.set_title('累计平均成绩走势', fontsize=14, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.3)
        for idx, val in enumerate(cumulative, start=1):
            if idx in (1, len(cumulative)) or idx % max(1, len(cumulative)//5) == 0:
                ax.text(idx, val + 1.5, f"{val:.1f}", ha='center', fontsize=9, fontweight='bold')
        plt.tight_layout()
        return fig

    def _infer_semester(self, exam_date: str):
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

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._is_destroyed = True
        super().closeEvent(event)
