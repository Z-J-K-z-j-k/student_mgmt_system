# client/pages/student_grade_analysis_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from ..utils.api_client import APIClient


class StudentGradeAnalysisPage(QWidget):
    def __init__(self, api: APIClient, user_id: int):
        super().__init__()
        self.api = api
        self.user_id = user_id
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

        # 图表展示区域标题
        charts_title = QLabel("📈 图表分析")
        charts_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f5f5f5; margin-top: 10px;")
        content_layout.addWidget(charts_title)

        # 图表容器 - 使用网格布局
        charts_grid = QGridLayout()
        charts_grid.setSpacing(20)

        # 柱状图区域
        bar_chart_label = QLabel("📊 每门课成绩（柱状图）")
        bar_chart_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f5f5f5;")
        charts_grid.addWidget(bar_chart_label, 0, 0)
        
        self.lbl_bar_chart = QLabel("等待数据加载...")
        self.lbl_bar_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_bar_chart.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                min-height: 350px;
                min-width: 500px;
            }
        """)
        self.lbl_bar_chart.setScaledContents(False)
        charts_grid.addWidget(self.lbl_bar_chart, 1, 0)

        # 饼图区域
        pie_chart_label = QLabel("🥧 成绩分布（饼图）")
        pie_chart_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f5f5f5;")
        charts_grid.addWidget(pie_chart_label, 0, 1)
        
        self.lbl_pie_chart = QLabel("等待数据加载...")
        self.lbl_pie_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pie_chart.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                min-height: 350px;
                min-width: 500px;
            }
        """)
        self.lbl_pie_chart.setScaledContents(False)
        charts_grid.addWidget(self.lbl_pie_chart, 1, 1)

        # 折线图区域（跨两列）
        line_chart_label = QLabel("📉 成绩随学期变化趋势（折线图）")
        line_chart_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f5f5f5;")
        charts_grid.addWidget(line_chart_label, 2, 0, 1, 2)
        
        self.lbl_line_chart = QLabel("等待数据加载...")
        self.lbl_line_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_line_chart.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                min-height: 350px;
            }
        """)
        self.lbl_line_chart.setScaledContents(False)
        charts_grid.addWidget(self.lbl_line_chart, 3, 0, 1, 2)

        content_layout.addLayout(charts_grid)
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

        # 延迟刷新，确保窗口完全初始化后再加载数据
        QTimer.singleShot(500, self.refresh)

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

    def safe_set_label_pixmap(self, label_name, pixmap):
        """安全地设置标签图片"""
        if not self.is_valid():
            return
        try:
            label = getattr(self, label_name, None)
            if label is not None and pixmap is not None and not pixmap.isNull():
                # 调整图片大小以适应标签
                scaled_pixmap = pixmap.scaled(
                    label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                label.setPixmap(scaled_pixmap)
        except (RuntimeError, AttributeError, Exception):
            pass

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
            self.safe_set_label_text("lbl_bar_chart", "正在生成图表...")
            self.safe_set_label_text("lbl_pie_chart", "正在生成图表...")
            self.safe_set_label_text("lbl_line_chart", "正在生成图表...")

            # 调用 API
            resp = self.api.get("/api/scores", params={"student_id": str(self.user_id)})
            
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
            QTimer.singleShot(300, self.generate_charts)

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
        self.safe_set_label_text("lbl_bar_chart", "暂无数据")
        self.safe_set_label_text("lbl_pie_chart", "暂无数据")
        self.safe_set_label_text("lbl_line_chart", "暂无数据")

    def generate_charts(self):
        """生成所有图表"""
        if not self.is_valid():
            return

        try:
            # 检查数据
            if not hasattr(self, 'scores_data') or not self.scores_data:
                self.clear_charts()
                return

            # 检查matplotlib是否可用
            try:
                import matplotlib
                matplotlib.use("Agg")  # 使用非交互式后端
                import matplotlib.pyplot as plt
                from io import BytesIO
            except ImportError:
                error_msg = "需要安装 matplotlib 库\n请运行: pip install matplotlib"
                self.safe_set_label_text("lbl_bar_chart", error_msg)
                self.safe_set_label_text("lbl_pie_chart", error_msg)
                self.safe_set_label_text("lbl_line_chart", error_msg)
                return

            # 配置中文字体
            try:
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans', 'Arial']
                plt.rcParams['axes.unicode_minus'] = False
            except:
                pass

            # 过滤有效成绩数据
            valid_data = []
            for s in self.scores_data:
                if not isinstance(s, dict):
                    continue
                score = s.get("score")
                if score is not None:
                    try:
                        score_val = float(score)
                        if 0 <= score_val <= 100:
                            valid_data.append({
                                "course_name": s.get("course_name", "未知课程"),
                                "score": score_val,
                                "semester": s.get("semester") or "未知学期"
                            })
                    except (ValueError, TypeError):
                        pass

            if not valid_data:
                self.clear_charts()
                return

            # 生成各个图表（独立处理异常）
            self.generate_bar_chart(valid_data)
            self.generate_pie_chart(valid_data)
            self.generate_line_chart(valid_data)

        except RuntimeError:
            # 对象已被删除，忽略
            pass
        except Exception as e:
            error_msg = f"生成图表失败：{str(e)}"
            self.safe_set_label_text("lbl_bar_chart", error_msg)
            self.safe_set_label_text("lbl_pie_chart", error_msg)
            self.safe_set_label_text("lbl_line_chart", error_msg)

    def generate_bar_chart(self, data):
        """生成柱状图：每门课成绩"""
        if not self.is_valid():
            return

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from io import BytesIO

            course_names = [d["course_name"] for d in data]
            scores = [d["score"] for d in data]

            # 如果课程名太长，截断
            course_names_short = [name[:12] + "..." if len(name) > 12 else name for name in course_names]

            fig, ax = plt.subplots(figsize=(12, 6))
            bars = ax.bar(range(len(course_names_short)), scores, color='#4CAF50', alpha=0.8, edgecolor='#2E7D32', linewidth=1.5)
            
            # 设置x轴标签
            ax.set_xticks(range(len(course_names_short)))
            ax.set_xticklabels(course_names_short, rotation=45, ha='right', fontsize=9)
            
            ax.set_ylabel('成绩', fontsize=12, fontweight='bold')
            ax.set_title('每门课成绩', fontsize=14, fontweight='bold', pad=15)
            ax.set_ylim(0, 105)
            ax.grid(True, alpha=0.3, axis='y', linestyle='--')

            # 在柱子上显示数值
            for i, (bar, score) in enumerate(zip(bars, scores)):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                       f'{score:.1f}',
                       ha='center', va='bottom', fontsize=9, fontweight='bold')

            plt.tight_layout()

            # 转换为图片
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            pixmap = QPixmap()
            if pixmap.loadFromData(buf.read()):
                self.safe_set_label_pixmap("lbl_bar_chart", pixmap)
            buf.close()
            plt.close(fig)

        except Exception as e:
            self.safe_set_label_text("lbl_bar_chart", f"生成柱状图失败：{str(e)}")

    def generate_pie_chart(self, data):
        """生成饼图：成绩分布"""
        if not self.is_valid():
            return

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from io import BytesIO

            scores = [d["score"] for d in data]
            
            # 统计各等级
            excellent = sum(1 for s in scores if s >= 90)
            good = sum(1 for s in scores if 80 <= s < 90)
            medium = sum(1 for s in scores if 70 <= s < 80)
            pass_count = sum(1 for s in scores if 60 <= s < 70)
            fail = sum(1 for s in scores if s < 60)

            labels = ['优秀\n(≥90)', '良好\n(80-89)', '中等\n(70-79)', '及格\n(60-69)', '不及格\n(<60)']
            sizes = [excellent, good, medium, pass_count, fail]
            colors = ['#4CAF50', '#8BC34A', '#FFC107', '#FF9800', '#F44336']
            
            # 过滤掉为0的项
            filtered_data = [(label, size, color) for label, size, color in zip(labels, sizes, colors) if size > 0]
            if not filtered_data:
                self.safe_set_label_text("lbl_pie_chart", "暂无数据")
                return

            labels_filtered, sizes_filtered, colors_filtered = zip(*filtered_data)

            fig, ax = plt.subplots(figsize=(9, 9))
            wedges, texts, autotexts = ax.pie(
                sizes_filtered, 
                labels=labels_filtered, 
                colors=colors_filtered,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 11, 'fontweight': 'bold'},
                explode=[0.05] * len(sizes_filtered)  # 分离各个扇形
            )
            
            # 美化百分比文本
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(10)
            
            ax.set_title('成绩分布', fontsize=16, fontweight='bold', pad=20)

            plt.tight_layout()

            # 转换为图片
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            pixmap = QPixmap()
            if pixmap.loadFromData(buf.read()):
                self.safe_set_label_pixmap("lbl_pie_chart", pixmap)
            buf.close()
            plt.close(fig)

        except Exception as e:
            self.safe_set_label_text("lbl_pie_chart", f"生成饼图失败：{str(e)}")

    def generate_line_chart(self, data):
        """生成折线图：成绩随学期变化趋势"""
        if not self.is_valid():
            return

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from io import BytesIO
            from collections import defaultdict

            # 按学期分组计算平均分
            semester_scores = defaultdict(list)
            for d in data:
                semester = str(d["semester"]).strip()
                if semester and semester != "未知学期":
                    semester_scores[semester].append(d["score"])

            if not semester_scores:
                self.safe_set_label_text("lbl_line_chart", "暂无学期数据")
                return

            # 计算每个学期的平均分
            semesters = sorted(semester_scores.keys())
            avg_scores = [sum(semester_scores[sem]) / len(semester_scores[sem]) for sem in semesters]

            fig, ax = plt.subplots(figsize=(14, 6))
            line = ax.plot(semesters, avg_scores, marker='o', linewidth=3, markersize=10, 
                          color='#2196F3', markerfacecolor='#1976D2', markeredgecolor='white', 
                          markeredgewidth=2, label='平均成绩')
            
            # 填充区域
            ax.fill_between(semesters, avg_scores, alpha=0.2, color='#2196F3')
            
            ax.set_xlabel('学期', fontsize=12, fontweight='bold')
            ax.set_ylabel('平均成绩', fontsize=12, fontweight='bold')
            ax.set_title('成绩随学期变化趋势', fontsize=14, fontweight='bold', pad=15)
            ax.set_ylim(0, 105)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.legend(loc='best', fontsize=10)

            # 在点上显示数值
            for sem, score in zip(semesters, avg_scores):
                ax.text(sem, score + 2, f'{score:.1f}',
                       ha='center', va='bottom', fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.5))

            # 旋转x轴标签
            plt.xticks(rotation=45, ha='right', fontsize=9)

            plt.tight_layout()

            # 转换为图片
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            pixmap = QPixmap()
            if pixmap.loadFromData(buf.read()):
                self.safe_set_label_pixmap("lbl_line_chart", pixmap)
            buf.close()
            plt.close(fig)

        except Exception as e:
            self.safe_set_label_text("lbl_line_chart", f"生成折线图失败：{str(e)}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._is_destroyed = True
        super().closeEvent(event)
