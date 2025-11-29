# client/pages/comprehensive_stats_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QScrollArea,
    QGroupBox, QGridLayout, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPixmap, QPalette
from ..utils.api_client import APIClient
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO

class ComprehensiveStatsPage(QWidget):
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api
        self.stats_data = None

        # 配置中文字体
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 标题区域（更紧凑）
        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90e2, stop:1 #357abd);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(12, 8, 12, 8)
        
        title = QLabel("📊 综合统计")
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: white;
            }
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #4a90e2;
                border: none;
                border-radius: 5px;
                padding: 6px 15px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        title_layout.addWidget(self.btn_refresh)
        main_layout.addWidget(title_frame)
        
        # 添加间距
        main_layout.addSpacing(10)

        # 创建滚动区域（只允许垂直滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 禁用水平滚动
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 需要时显示垂直滚动
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f7fa;
            }
        """)
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #f5f7fa;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # 统计信息卡片区域（使用网格布局，更紧凑）
        stats_section_label = QLabel("📈 数据概览")
        stats_section_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px 0;
            }
        """)
        content_layout.addWidget(stats_section_label)
        
        self.stats_container = QWidget()
        self.stats_layout = QGridLayout(self.stats_container)
        self.stats_layout.setSpacing(10)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stats_container)
        
        # 添加分隔线（更紧凑）
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #ddd; margin: 10px 0;")
        separator.setFixedHeight(1)
        content_layout.addWidget(separator)

        # 图表区域（使用网格布局，更紧凑）
        charts_section_label = QLabel("📊 可视化图表")
        charts_section_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px 0;
            }
        """)
        content_layout.addWidget(charts_section_label)
        
        self.charts_container = QWidget()
        self.charts_layout = QGridLayout(self.charts_container)
        self.charts_layout.setSpacing(10)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.charts_container)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, 1)  # 使用stretch factor让内容填充剩余空间

        # 初始加载
        self.refresh()

    def refresh(self):
        """刷新统计数据"""
        try:
            resp = self.api.get("/api/stats/comprehensive")
            data = resp.json()
            if data.get("status") != "ok":
                QMessageBox.warning(self, "错误", data.get("msg", "获取统计失败"))
                return
            
            self.stats_data = data.get("data", {})
            self.render_stats()
            self.render_charts()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取统计数据失败：{e}")

    def render_stats(self):
        """渲染统计信息卡片"""
        # 清空现有内容
        while self.stats_layout.count():
            child = self.stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.stats_data:
            return

        # 创建统计卡片
        cards = []

        # 用户统计
        if "users" in self.stats_data:
            users = self.stats_data["users"]
            cards.append(self.create_stat_card("👥 用户统计", [
                ("总用户数", str(users.get("total", 0))),
                ("按角色分布", self.format_dict(users.get("by_role", {})))
            ]))

        # 学生统计
        if "students" in self.stats_data:
            students = self.stats_data["students"]
            cards.append(self.create_stat_card("🧍‍♂️ 学生统计", [
                ("总学生数", str(students.get("total", 0))),
                ("按专业分布", self.format_dict(students.get("by_major", {}))),
                ("按年级分布", self.format_dict(students.get("by_grade", {}))),
                ("按性别分布", self.format_dict(students.get("by_gender", {})))
            ]))

        # 教师统计
        if "teachers" in self.stats_data:
            teachers = self.stats_data["teachers"]
            cards.append(self.create_stat_card("👨‍🏫 教师统计", [
                ("总教师数", str(teachers.get("total", 0))),
                ("按学院分布", self.format_dict(teachers.get("by_department", {})))
            ]))

        # 课程统计
        if "courses" in self.stats_data:
            courses = self.stats_data["courses"]
            cards.append(self.create_stat_card("📚 课程统计", [
                ("总课程数", str(courses.get("total", 0))),
                ("按学期分布", self.format_dict(courses.get("by_semester", {})))
            ]))

        # 选课统计
        if "course_selection" in self.stats_data:
            selection = self.stats_data["course_selection"]
            cards.append(self.create_stat_card("📝 选课统计", [
                ("总选课记录数", str(selection.get("total", 0))),
                ("按学期分布", self.format_dict(selection.get("by_semester", {})))
            ]))

        # 成绩统计
        if "scores" in self.stats_data:
            scores = self.stats_data["scores"]
            avg_score = scores.get("avg_score")
            avg_text = f"{avg_score:.2f}" if avg_score else "暂无数据"
            cards.append(self.create_stat_card("📊 成绩统计", [
                ("总成绩记录数", str(scores.get("total", 0))),
                ("有效成绩数", str(scores.get("valid_scores", 0))),
                ("平均分", avg_text),
                ("分数段分布", self.format_dict(scores.get("score_distribution", {})))
            ]))

        # 教室统计
        if "classrooms" in self.stats_data:
            classrooms = self.stats_data["classrooms"]
            cards.append(self.create_stat_card("🏫 教室统计", [
                ("总教室数", str(classrooms.get("total", 0))),
                ("总容量", str(classrooms.get("total_capacity", 0))),
                ("按楼栋分布", self.format_dict(classrooms.get("by_building", {})))
            ]))

        # 课程安排统计
        if "course_schedule" in self.stats_data:
            schedule = self.stats_data["course_schedule"]
            cards.append(self.create_stat_card("📅 课程安排统计", [
                ("总安排数", str(schedule.get("total", 0))),
                ("按学期分布", self.format_dict(schedule.get("by_semester", {}))),
                ("按星期分布", self.format_dict(schedule.get("by_day", {})))
            ]))

        # 使用网格布局，每行2个
        # 设置列拉伸，确保不会水平溢出
        for i in range(2):
            self.stats_layout.setColumnStretch(i, 1)
        
        for i, card in enumerate(cards):
            row = i // 2
            col = i % 2
            self.stats_layout.addWidget(card, row, col)

    def create_stat_card(self, title, items):
        """创建统计卡片（更紧凑版本）"""
        # 卡片颜色方案
        card_colors = [
            ("#4a90e2", "#e8f4fd"),  # 蓝色
            ("#50c878", "#e8f8f0"),  # 绿色
            ("#ff6b6b", "#ffe8e8"),  # 红色
            ("#ffa500", "#fff4e6"),  # 橙色
            ("#9b59b6", "#f4ecf7"),  # 紫色
            ("#1abc9c", "#e8f8f5"),  # 青色
            ("#e74c3c", "#fadbd8"),  # 深红
            ("#3498db", "#ebf5fb"),  # 天蓝
        ]
        
        # 根据标题选择颜色
        color_index = hash(title) % len(card_colors)
        border_color, bg_color = card_colors[color_index]
        
        group = QGroupBox(title)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                border: 2px solid {border_color};
                border-radius: 8px;
                margin-top: 5px;
                padding-top: 10px;
                background-color: {bg_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {border_color};
            }}
        """)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 15, 10, 10)

        for label, value in items:
            item_frame = QFrame()
            item_frame.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
            item_layout = QHBoxLayout(item_frame)
            item_layout.setContentsMargins(8, 4, 8, 4)
            
            label_widget = QLabel(f"{label}：")
            label_widget.setStyleSheet("""
                QLabel {
                    font-weight: normal;
                    font-size: 11px;
                    color: #666;
                    min-width: 80px;
                }
            """)
            
            value_widget = QLabel(str(value))
            value_widget.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    font-size: 12px;
                    color: #2c3e50;
                }
            """)
            value_widget.setWordWrap(True)
            
            item_layout.addWidget(label_widget)
            item_layout.addWidget(value_widget, 1)
            layout.addWidget(item_frame)

        return group

    def format_dict(self, d):
        """格式化字典为字符串"""
        if not d:
            return "暂无数据"
        # 如果项目太多，只显示前5个
        items_list = list(d.items())
        if len(items_list) > 5:
            items = [f"{k}: {v}" for k, v in items_list[:5]]
            items.append(f"... 等{len(items_list)}项")
        else:
            items = [f"{k}: {v}" for k, v in items_list]
        return " | ".join(items)

    def render_charts(self):
        """渲染图表"""
        # 清空现有内容
        while self.charts_layout.count():
            child = self.charts_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.stats_data:
            return

        # 创建图表
        charts = []

        # 学生专业分布饼图
        if "students" in self.stats_data and self.stats_data["students"].get("by_major"):
            charts.append(self.create_chart_widget("学生专业分布", 
                self.stats_data["students"]["by_major"], "pie"))

        # 成绩分布饼图
        if "scores" in self.stats_data and self.stats_data["scores"].get("score_distribution"):
            charts.append(self.create_chart_widget("成绩分布", 
                self.stats_data["scores"]["score_distribution"], "pie"))

        # 教室楼栋分布柱状图
        if "classrooms" in self.stats_data and self.stats_data["classrooms"].get("by_building"):
            charts.append(self.create_chart_widget("教室楼栋分布", 
                self.stats_data["classrooms"]["by_building"], "bar"))

        # 课程安排星期分布柱状图
        if "course_schedule" in self.stats_data and self.stats_data["course_schedule"].get("by_day"):
            charts.append(self.create_chart_widget("课程安排星期分布", 
                self.stats_data["course_schedule"]["by_day"], "bar"))

        # 使用网格布局，每行2个图表
        # 设置列拉伸，确保不会水平溢出
        for i in range(2):
            self.charts_layout.setColumnStretch(i, 1)
        
        for i, chart in enumerate(charts):
            row = i // 2
            col = i % 2
            self.charts_layout.addWidget(chart, row, col)

    def create_chart_widget(self, title, data, chart_type="bar"):
        """创建图表组件（更紧凑版本）"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 5px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2c3e50;
            }
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 15, 8, 8)

        try:
            # 生成图表（更小尺寸以适应屏幕）
            fig, ax = plt.subplots(figsize=(5, 3.5))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('#fafafa')
            
            if chart_type == "pie":
                labels = list(data.keys())
                values = list(data.values())
                
                # 使用更美观的颜色方案
                colors = ['#4a90e2', '#50c878', '#ff6b6b', '#ffa500', '#9b59b6', 
                         '#1abc9c', '#e74c3c', '#3498db', '#f39c12', '#16a085']
                if len(labels) > len(colors):
                    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
                
                wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%', 
                                                   colors=colors[:len(labels)], startangle=90,
                                                   textprops={'fontsize': 9, 'fontweight': 'bold'})
                
                # 美化百分比文字
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                
                ax.set_title(title, fontsize=12, fontweight='bold', pad=10, color='#2c3e50')
                plt.setp(texts, fontsize=9)
                
            else:  # bar
                labels = list(data.keys())
                values = list(data.values())
                
                # 使用渐变色
                colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(labels)))
                bars = ax.bar(labels, values, color=colors, edgecolor='white', linewidth=1.5)
                
                ax.set_title(title, fontsize=12, fontweight='bold', pad=10, color='#2c3e50')
                ax.set_xlabel('', fontsize=9)
                ax.set_ylabel('数量', fontsize=9, fontweight='bold')
                ax.tick_params(axis='x', rotation=45, labelsize=8)
                ax.tick_params(axis='y', labelsize=8)
                
                # 添加网格线
                ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
                ax.set_axisbelow(True)
                
                # 在柱状图上显示数值
                max_val = max(values) if values else 1
                for bar, value in zip(bars, values):
                    if value > 0:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2, height + max_val*0.02,
                               str(value), ha='center', va='bottom', 
                               fontsize=8, fontweight='bold', color='#2c3e50')
            
            plt.tight_layout()
            
            # 转换为QPixmap
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.read())
            buf.close()
            plt.close()

            # 创建标签显示图表
            chart_label = QLabel()
            chart_label.setPixmap(pixmap)
            chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chart_label.setStyleSheet("""
                QLabel {
                    background-color: white;
                    border-radius: 8px;
                    padding: 5px;
                }
            """)
            layout.addWidget(chart_label)
        except Exception as e:
            error_label = QLabel(f"图表生成失败：{str(e)}")
            error_label.setStyleSheet("""
                QLabel {
                    color: #e74c3c;
                    font-size: 12px;
                    padding: 10px;
                    background-color: #fadbd8;
                    border-radius: 6px;
                }
            """)
            layout.addWidget(error_label)

        return group

