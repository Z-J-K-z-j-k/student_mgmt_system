# client/pages/stats_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QMessageBox, 
    QFrame, QGridLayout, QTabWidget, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont, QColor
import requests
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from io import BytesIO
from ..utils.api_client import APIClient, SERVER_URL

# 配置 Matplotlib 中文字体
def setup_chinese_font():
    """配置 Matplotlib 支持中文显示"""
    import platform
    system = platform.system()
    
    if system == 'Windows':
        # Windows 系统常用中文字体
        fonts = ['Microsoft YaHei', 'SimHei', 'KaiTi', 'FangSong']
    elif system == 'Darwin':  # macOS
        fonts = ['Arial Unicode MS', 'PingFang SC', 'STHeiti']
    else:  # Linux
        fonts = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'Droid Sans Fallback']
    
    # 尝试设置字体
    for font in fonts:
        try:
            plt.rcParams['font.sans-serif'] = [font] + plt.rcParams['font.sans-serif']
            break
        except:
            continue
    
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 初始化字体配置
setup_chinese_font()


class StatsPage(QWidget):
    def __init__(self, api: APIClient, role: str = "admin", user_id: int = None):
        super().__init__()
        self.api = api
        self.role = role
        self.user_id = user_id

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 如果是教师角色，显示课程选择界面
        if self.role == "teacher":
            self.setup_teacher_view(layout)
        else:
            # 管理员视图（保留原有功能）
            self.setup_admin_view(layout)

    def setup_teacher_view(self, layout):
        """教师视图：课程选择和统计"""
        # 标题
        title = QLabel("📊 课程统计")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        layout.addWidget(title)

        # 课程选择栏（顶部）
        course_frame = QFrame()
        course_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        course_layout = QHBoxLayout(course_frame)
        course_layout.setContentsMargins(15, 10, 15, 10)
        
        course_layout.addWidget(QLabel("选择课程："))
        
        self.course_combo = QComboBox()
        self.course_combo.setMinimumWidth(300)
        self.course_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
        """)
        self.course_combo.currentIndexChanged.connect(self.on_course_selected)
        self._loading_courses = False
        course_layout.addWidget(self.course_combo)
        
        self.btn_refresh = QPushButton("刷新统计")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 14px;
                min-height: 36px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        def on_refresh_clicked():
            self._user_clicked_refresh = True
            self.load_course_stats()
        self.btn_refresh.clicked.connect(on_refresh_clicked)
        self._user_clicked_refresh = False
        
        course_layout.addWidget(self.btn_refresh)
        course_layout.addStretch()
        
        layout.addWidget(course_frame)

        # 主要内容区域（左右布局）
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # 左侧：统计卡片和表格
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 统计数字卡片区
        cards_frame = QFrame()
        cards_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setSpacing(15)

        # 创建统计卡片
        self.card_labels = {}
        card_items = [
            ("平均分", "avg_score", "{:.2f}"),
            ("最高分", "max_score", "{:.0f}"),
            ("最低分", "min_score", "{:.0f}"),
            ("及格率", "pass_rate", "{:.1f}%"),
            ("总人数", "total", "{}"),
        ]

        for idx, (label, key, fmt) in enumerate(card_items):
            row = idx // 3
            col = idx % 3
            
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #f5f5f5;
                    border-radius: 6px;
                    padding: 12px;
                    min-width: 120px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(5)
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #666; font-size: 12px;")
            card_layout.addWidget(label_widget)
            
            value_widget = QLabel("--")
            value_widget.setStyleSheet("color: #1f1f1f; font-size: 18px; font-weight: bold;")
            self.card_labels[key] = (value_widget, fmt)
            card_layout.addWidget(value_widget)
            
            cards_layout.addWidget(card, row, col)

        left_layout.addWidget(cards_frame)

        # 统计表格
        table_frame = QFrame()
        table_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        table_title = QLabel("分数段分布")
        table_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        table_layout.addWidget(table_title)

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["分数段", "人数"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                gridline-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 8px;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        self.stats_table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.stats_table)

        left_layout.addWidget(table_frame)
        left_layout.addStretch()

        content_layout.addWidget(left_widget, 1)

        # 右侧：图表区域
        chart_frame = QFrame()
        chart_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        chart_title = QLabel("分数段分布图")
        chart_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        chart_layout.addWidget(chart_title)

        self.chart_label = QLabel("请选择课程查看统计")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_label.setMinimumSize(500, 400)
        self.chart_label.setStyleSheet("""
            QLabel {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
                color: #999;
            }
        """)
        chart_layout.addWidget(self.chart_label)

        content_layout.addWidget(chart_frame, 1)

        layout.addLayout(content_layout)
        layout.addStretch()

        # 加载课程列表
        self.load_courses()

    def setup_admin_view(self, layout):
        """管理员视图：综合统计（数据分析 + 可视化）"""
        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f5f5f5;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #2196F3;
            }
        """)
        
        # 1. 全校成绩统计
        self.tab_school = self.create_school_stats_tab()
        self.tabs.addTab(self.tab_school, "📊 全校成绩统计")
        
        # 2. 专业/年级趋势
        self.tab_trends = self.create_trends_tab()
        self.tabs.addTab(self.tab_trends, "📈 专业/年级趋势")
        
        # 3. 数据清洗报告
        self.tab_quality = self.create_data_quality_tab()
        self.tabs.addTab(self.tab_quality, "🔍 数据清洗报告")
        
        layout.addWidget(self.tabs)
        
        # 初始加载数据
        self.load_admin_data()
    
    def create_school_stats_tab(self):
        """创建全校成绩统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和刷新按钮
        header = QHBoxLayout()
        title = QLabel("📊 全校成绩统计")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        header.addWidget(title)
        header.addStretch()
        
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        btn_refresh.clicked.connect(self.load_school_stats)
        header.addWidget(btn_refresh)
        layout.addLayout(header)
        
        # 统计卡片
        cards_frame = QFrame()
        cards_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setSpacing(15)
        
        self.school_cards = {}
        card_items = [
            ("全校平均分", "avg_score", "{:.2f}分"),
            ("及格率", "pass_rate", "{:.1f}%"),
            ("优秀率", "excellent_rate", "{:.1f}%"),
            ("总学生数", "total_students", "{}人"),
            ("总成绩记录", "total_records", "{}条"),
        ]
        
        for idx, (label, key, fmt) in enumerate(card_items):
            row = idx // 3
            col = idx % 3
            
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #f5f5f5;
                    border-radius: 6px;
                    padding: 15px;
                    min-width: 150px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(5)
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #666; font-size: 12px;")
            card_layout.addWidget(label_widget)
            
            value_widget = QLabel("--")
            value_widget.setStyleSheet("color: #1f1f1f; font-size: 20px; font-weight: bold;")
            self.school_cards[key] = (value_widget, fmt)
            card_layout.addWidget(value_widget)
            
            cards_layout.addWidget(card, row, col)
        
        layout.addWidget(cards_frame)
        
        # 内容区域（左右布局）
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # 左侧：最高分前十学生表格
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        table_title = QLabel("🏆 最高分前十学生")
        table_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        left_layout.addWidget(table_title)
        
        self.top_students_table = QTableWidget()
        self.top_students_table.setColumnCount(5)
        self.top_students_table.setHorizontalHeaderLabels(["排名", "学号", "姓名", "专业", "加权平均分"])
        self.top_students_table.horizontalHeader().setStretchLastSection(True)
        self.top_students_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                gridline-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 8px;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        self.top_students_table.verticalHeader().setVisible(False)
        left_layout.addWidget(self.top_students_table)
        
        content_layout.addWidget(left_widget, 1)
        
        # 右侧：图表
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        chart_title = QLabel("📈 课程平均分对比")
        chart_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        right_layout.addWidget(chart_title)
        
        self.course_comparison_chart = QLabel("加载中...")
        self.course_comparison_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.course_comparison_chart.setMinimumSize(600, 400)
        self.course_comparison_chart.setStyleSheet("""
            QLabel {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        right_layout.addWidget(self.course_comparison_chart)
        
        content_layout.addWidget(right_widget, 1)
        
        layout.addLayout(content_layout)
        layout.addStretch()
        
        return widget
    
    def create_trends_tab(self):
        """创建专业/年级趋势标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和刷新按钮
        header = QHBoxLayout()
        title = QLabel("📈 专业/年级学习情况趋势")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        header.addWidget(title)
        header.addStretch()
        
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        btn_refresh.clicked.connect(self.load_trends_data)
        header.addWidget(btn_refresh)
        layout.addLayout(header)
        
        # 图表区域（上下布局）
        charts_layout = QVBoxLayout()
        charts_layout.setSpacing(20)
        
        # 专业平均分柱状图
        major_frame = QFrame()
        major_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        major_layout = QVBoxLayout(major_frame)
        major_layout.setContentsMargins(0, 0, 0, 0)
        
        major_title = QLabel("📊 各专业平均分对比（柱状图）")
        major_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        major_layout.addWidget(major_title)
        
        self.major_chart = QLabel("加载中...")
        self.major_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.major_chart.setMinimumSize(800, 400)
        self.major_chart.setStyleSheet("""
            QLabel {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        major_layout.addWidget(self.major_chart)
        
        charts_layout.addWidget(major_frame)
        
        # 年级趋势折线图
        grade_frame = QFrame()
        grade_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        grade_layout = QVBoxLayout(grade_frame)
        grade_layout.setContentsMargins(0, 0, 0, 0)
        
        grade_title = QLabel("📈 各年级学习情况趋势（折线图）")
        grade_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        grade_layout.addWidget(grade_title)
        
        self.grade_chart = QLabel("加载中...")
        self.grade_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grade_chart.setMinimumSize(800, 400)
        self.grade_chart.setStyleSheet("""
            QLabel {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        grade_layout.addWidget(self.grade_chart)
        
        charts_layout.addWidget(grade_frame)
        
        layout.addLayout(charts_layout)
        layout.addStretch()
        
        return widget
    
    def create_data_quality_tab(self):
        """创建数据清洗报告标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和刷新按钮
        header = QHBoxLayout()
        title = QLabel("🔍 数据清洗报告")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        header.addWidget(title)
        header.addStretch()
        
        btn_refresh = QPushButton("🔄 刷新检测")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        btn_refresh.clicked.connect(self.load_data_quality)
        header.addWidget(btn_refresh)
        
        layout.addLayout(header)
        
        # 统计信息
        info_label = QLabel("检测到 0 条异常数据")
        info_label.setStyleSheet("font-size: 14px; color: #666; margin-bottom: 10px;")
        self.quality_info_label = info_label
        layout.addWidget(info_label)
        
        # 异常数据表格
        self.quality_table = QTableWidget()
        self.quality_table.setColumnCount(5)
        self.quality_table.setHorizontalHeaderLabels(["类型", "学号", "姓名", "问题描述", "严重程度"])
        self.quality_table.horizontalHeader().setStretchLastSection(True)
        self.quality_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                gridline-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 8px;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        self.quality_table.verticalHeader().setVisible(False)
        layout.addWidget(self.quality_table)
        
        return widget
    
    def load_admin_data(self):
        """加载所有管理员统计数据"""
        self.load_school_stats()
        self.load_trends_data()
        self.load_data_quality()
    
    def load_school_stats(self):
        """加载全校成绩统计"""
        try:
            # 加载统计数字
            resp = self.api.get("/api/stats/school")
            if resp.status_code != 200:
                error_msg = f"HTTP {resp.status_code}"
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", error_msg)
                except:
                    pass
                QMessageBox.warning(self, "错误", f"获取全校统计失败：{error_msg}")
                return
            
            data = resp.json()
            if data.get("status") != "ok":
                error_msg = data.get("msg", "未知错误")
                QMessageBox.warning(self, "错误", f"获取全校统计失败：{error_msg}")
                return
            
            stats = data.get("data", {})
            if not stats:
                QMessageBox.information(self, "提示", "暂无统计数据")
                return
            
            # 更新卡片
            if "avg_score" in self.school_cards:
                avg = stats.get("avg_score")
                try:
                    avg = float(avg) if avg is not None else None
                    if avg is not None:
                        self.school_cards["avg_score"][0].setText(f"{avg:.2f}分")
                    else:
                        self.school_cards["avg_score"][0].setText("N/A")
                except (ValueError, TypeError):
                    self.school_cards["avg_score"][0].setText("N/A")
            
            if "pass_rate" in self.school_cards:
                try:
                    rate = stats.get("pass_rate", 0)
                    rate = float(rate) * 100 if rate is not None else 0
                    self.school_cards["pass_rate"][0].setText(f"{rate:.1f}%")
                except (ValueError, TypeError):
                    self.school_cards["pass_rate"][0].setText("0.0%")
            
            if "excellent_rate" in self.school_cards:
                try:
                    rate = stats.get("excellent_rate", 0)
                    rate = float(rate) * 100 if rate is not None else 0
                    self.school_cards["excellent_rate"][0].setText(f"{rate:.1f}%")
                except (ValueError, TypeError):
                    self.school_cards["excellent_rate"][0].setText("0.0%")
            
            if "total_students" in self.school_cards:
                try:
                    total = int(stats.get("total_students", 0))
                    self.school_cards["total_students"][0].setText(f"{total}人")
                except (ValueError, TypeError):
                    self.school_cards["total_students"][0].setText("0人")
            
            if "total_records" in self.school_cards:
                try:
                    total = int(stats.get("total_records", 0))
                    self.school_cards["total_records"][0].setText(f"{total}条")
                except (ValueError, TypeError):
                    self.school_cards["total_records"][0].setText("0条")
            
            # 加载最高分前十学生
            try:
                print(f"[DEBUG] 开始调用API: /api/stats/top_students")
                resp = self.api.get("/api/stats/top_students", params={"limit": 10})
                print(f"[DEBUG] API响应状态码: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"[DEBUG] API返回数据: status={data.get('status')}, data长度={len(data.get('data', []))}")
                    if data.get("status") == "ok":
                        students = data.get("data", [])
                        print(f"[DEBUG] 学生数据: {len(students)} 条")
                        if students:
                            self.top_students_table.setRowCount(len(students))
                            for i, s in enumerate(students):
                                self.top_students_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                                self.top_students_table.setItem(i, 1, QTableWidgetItem(str(s.get("student_id", ""))))
                                self.top_students_table.setItem(i, 2, QTableWidgetItem(str(s.get("student_name", ""))))
                                self.top_students_table.setItem(i, 3, QTableWidgetItem(str(s.get("major", ""))))
                                try:
                                    avg_score = s.get("avg_score", 0)
                                    avg_score = float(avg_score) if avg_score is not None else 0.0
                                    self.top_students_table.setItem(i, 4, QTableWidgetItem(f"{avg_score:.2f}"))
                                except (ValueError, TypeError):
                                    self.top_students_table.setItem(i, 4, QTableWidgetItem("0.00"))
                        else:
                            # 没有数据，显示提示
                            self.top_students_table.setRowCount(1)
                            self.top_students_table.setItem(0, 0, QTableWidgetItem("暂无数据"))
                            self.top_students_table.setItem(0, 1, QTableWidgetItem(""))
                            self.top_students_table.setItem(0, 2, QTableWidgetItem(""))
                            self.top_students_table.setItem(0, 3, QTableWidgetItem(""))
                            self.top_students_table.setItem(0, 4, QTableWidgetItem(""))
                    else:
                        # API返回错误
                        error_msg = data.get("msg", "未知错误")
                        self.top_students_table.setRowCount(1)
                        self.top_students_table.setItem(0, 0, QTableWidgetItem(f"加载失败: {error_msg}"))
                        self.top_students_table.setItem(0, 1, QTableWidgetItem(""))
                        self.top_students_table.setItem(0, 2, QTableWidgetItem(""))
                        self.top_students_table.setItem(0, 3, QTableWidgetItem(""))
                        self.top_students_table.setItem(0, 4, QTableWidgetItem(""))
                else:
                    # HTTP错误
                    error_msg = f"HTTP {resp.status_code}"
                    try:
                        error_data = resp.json()
                        error_msg = error_data.get("msg", error_msg)
                    except:
                        pass
                    self.top_students_table.setRowCount(1)
                    self.top_students_table.setItem(0, 0, QTableWidgetItem(f"请求失败: {error_msg}"))
                    self.top_students_table.setItem(0, 1, QTableWidgetItem(""))
                    self.top_students_table.setItem(0, 2, QTableWidgetItem(""))
                    self.top_students_table.setItem(0, 3, QTableWidgetItem(""))
                    self.top_students_table.setItem(0, 4, QTableWidgetItem(""))
            except Exception as e:
                # 异常处理
                import traceback
                error_detail = traceback.format_exc()
                self.top_students_table.setRowCount(1)
                self.top_students_table.setItem(0, 0, QTableWidgetItem(f"加载异常: {str(e)}"))
                self.top_students_table.setItem(0, 1, QTableWidgetItem(""))
                self.top_students_table.setItem(0, 2, QTableWidgetItem(""))
                self.top_students_table.setItem(0, 3, QTableWidgetItem(""))
                self.top_students_table.setItem(0, 4, QTableWidgetItem(""))
                print(f"加载最高分学生失败: {error_detail}")
            
            # 加载课程对比图表
            try:
                url = f"{SERVER_URL}/api/charts/course_comparison.png"
                resp = requests.get(url, timeout=10, headers=self.api._headers())
                if resp.status_code == 200:
                    pix = QPixmap()
                    pix.loadFromData(resp.content)
                    self.course_comparison_chart.setPixmap(pix.scaled(600, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    self.course_comparison_chart.setText("图表加载失败")
            except Exception as e:
                self.course_comparison_chart.setText(f"图表加载失败：{str(e)}")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            QMessageBox.critical(self, "错误", f"加载全校统计失败：{str(e)}\n\n{error_detail}")
    
    def load_trends_data(self):
        """加载专业/年级趋势数据"""
        try:
            # 加载专业图表
            url = f"{SERVER_URL}/api/charts/major_avg_bar.png"
            resp = requests.get(url, timeout=10, headers=self.api._headers())
            if resp.status_code == 200:
                pix = QPixmap()
                pix.loadFromData(resp.content)
                self.major_chart.setPixmap(pix.scaled(800, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.major_chart.setText("专业图表加载失败")
            
            # 加载年级图表
            url = f"{SERVER_URL}/api/charts/grade_trend.png"
            resp = requests.get(url, timeout=10, headers=self.api._headers())
            if resp.status_code == 200:
                pix = QPixmap()
                pix.loadFromData(resp.content)
                self.grade_chart.setPixmap(pix.scaled(800, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.grade_chart.setText("年级图表加载失败")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载趋势数据失败：{str(e)}")
    
    def load_data_quality(self):
        """加载数据质量检测报告"""
        try:
            resp = self.api.get("/api/stats/data_quality")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    issues = data.get("data", [])
                    count = data.get("count", 0)
                    
                    # 更新统计信息
                    self.quality_info_label.setText(f"检测到 {count} 条异常数据")
                    
                    # 更新表格
                    self.quality_table.setRowCount(len(issues))
                    for i, issue in enumerate(issues):
                        # 严重程度颜色
                        severity = issue.get("severity", "info")
                        color = "#666"
                        if severity == "error":
                            color = "#f44336"
                        elif severity == "warning":
                            color = "#ff9800"
                        
                        self.quality_table.setItem(i, 0, QTableWidgetItem(issue.get("type", "")))
                        student_id = issue.get("student_id")
                        self.quality_table.setItem(i, 1, QTableWidgetItem(str(student_id) if student_id else "N/A"))
                        self.quality_table.setItem(i, 2, QTableWidgetItem(issue.get("student_name", "")))
                        self.quality_table.setItem(i, 3, QTableWidgetItem(issue.get("issue", "")))
                        
                        severity_item = QTableWidgetItem(issue.get("severity", "info").upper())
                        # 设置颜色
                        if severity == "error":
                            severity_item.setForeground(QColor("#f44336"))
                        elif severity == "warning":
                            severity_item.setForeground(QColor("#ff9800"))
                        else:
                            severity_item.setForeground(QColor("#666"))
                        self.quality_table.setItem(i, 4, severity_item)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载数据质量报告失败：{str(e)}")

    def load_courses(self):
        """加载教师教授的课程列表"""
        try:
            self._loading_courses = True
            resp = self.api.get("/api/teacher/my-courses")
            if resp.status_code != 200:
                self.show_error(f"获取课程列表失败：HTTP {resp.status_code}")
                self._loading_courses = False
                return
            
            data = resp.json()
            if data.get("status") != "ok":
                self.show_error(f"获取课程列表失败：{data.get('msg', '未知错误')}")
                self._loading_courses = False
                return

            courses = data.get("data", [])
            self.course_combo.clear()
            for course in courses:
                course_id = course.get("course_id")
                course_name = course.get("course_name", "")
                self.course_combo.addItem(f"{course_name} (ID: {course_id})", course_id)

            self._loading_courses = False
            
            if courses:
                # 自动加载第一门课程的统计
                self.load_course_stats()
            else:
                self.chart_label.setText("您目前没有教授的课程")
        except Exception as e:
            self._loading_courses = False
            self.show_error(f"加载课程列表失败：{str(e)}")

    def show_error(self, message):
        """显示错误信息（使用弹窗）"""
        QMessageBox.warning(self, "错误", message)

    def on_course_selected(self, index):
        """课程选择改变时加载统计"""
        if self._loading_courses:
            return
        if index >= 0 and self.course_combo.currentData():
            self.load_course_stats()

    def load_course_stats(self):
        """加载选中课程的统计信息"""
        course_id = self.course_combo.currentData()
        if not course_id:
            self.chart_label.setText("请选择课程")
            self.stats_table.setRowCount(0)
            self.clear_cards()
            return

        try:
            resp = self.api.get("/api/teacher/course_stats", params={"course_id": course_id})
            if resp.status_code != 200:
                error_msg = f"获取统计信息失败：HTTP {resp.status_code}"
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", error_msg)
                except:
                    pass
                self.show_error(error_msg)
                self.chart_label.setText("获取数据失败")
                self.stats_table.setRowCount(0)
                self.clear_cards()
                return

            data = resp.json()
            if data.get("status") != "ok":
                error_msg = data.get("msg", "未知错误")
                self.show_error(f"获取统计信息失败：{error_msg}")
                self.chart_label.setText("获取数据失败")
                self.stats_table.setRowCount(0)
                self.clear_cards()
                return

            stats = data.get("data", {})
            self.display_stats(stats)
            self.draw_chart(stats)
        except Exception as e:
            error_msg = f"获取统计信息失败：{str(e)}"
            if self._user_clicked_refresh:
                import traceback
                QMessageBox.critical(self, "错误", f"{error_msg}\n\n{traceback.format_exc()}")
                self._user_clicked_refresh = False
            else:
                self.show_error(error_msg)
            self.chart_label.setText("获取数据失败")
            self.stats_table.setRowCount(0)
            self.clear_cards()

    def clear_cards(self):
        """清空统计卡片"""
        for key, (widget, fmt) in self.card_labels.items():
            widget.setText("--")

    def safe_float(self, value, default=0.0):
        """安全地将值转换为浮点数"""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def display_stats(self, stats):
        """在表格和卡片中显示统计信息"""
        # 更新统计卡片
        avg_score = self.safe_float(stats.get("avg_score"))
        min_score = self.safe_float(stats.get("min_score"))
        max_score = self.safe_float(stats.get("max_score"))
        pass_rate = self.safe_float(stats.get("pass_rate", 0))
        total = stats.get("total", 0)
        try:
            total = int(total)
        except (ValueError, TypeError):
            total = 0

        # 更新卡片显示
        if avg_score > 0 or stats.get("avg_score") is not None:
            self.card_labels["avg_score"][0].setText(f"{avg_score:.2f}")
        else:
            self.card_labels["avg_score"][0].setText("N/A")

        if min_score > 0 or stats.get("min_score") is not None:
            self.card_labels["min_score"][0].setText(f"{min_score:.0f}")
        else:
            self.card_labels["min_score"][0].setText("N/A")

        if max_score > 0 or stats.get("max_score") is not None:
            self.card_labels["max_score"][0].setText(f"{max_score:.0f}")
        else:
            self.card_labels["max_score"][0].setText("N/A")

        self.card_labels["pass_rate"][0].setText(f"{pass_rate * 100:.1f}%")
        self.card_labels["total"][0].setText(str(total))

        # 更新分数段分布表格
        bins = stats.get("bins", {})
        rows = [
            ("0-59分", bins.get("0-59", 0)),
            ("60-69分", bins.get("60-69", 0)),
            ("70-79分", bins.get("70-79", 0)),
            ("80-89分", bins.get("80-89", 0)),
            ("90-100分", bins.get("90-100", 0)),
        ]

        self.stats_table.setRowCount(len(rows))
        for i, (label, value) in enumerate(rows):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            # 使用 QFont 设置粗体，而不是 setStyleSheet
            if i == 0:  # 第一行作为标题
                font = QFont()
                font.setBold(True)
                label_item.setFont(font)
            self.stats_table.setItem(i, 0, label_item)

            value_item = QTableWidgetItem(str(value))
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.stats_table.setItem(i, 1, value_item)

    def draw_chart(self, stats):
        """绘制分数段分布柱状图"""
        bins = stats.get("bins", {})
        if not bins:
            self.chart_label.setText("暂无数据")
            return

        # 确保中文字体配置
        setup_chinese_font()

        # 准备数据，确保值为数字类型
        labels = list(bins.keys())
        values = []
        for label in labels:
            val = bins.get(label, 0)
            try:
                values.append(int(val))
            except (ValueError, TypeError):
                values.append(0)

        # 创建图表
        plt.figure(figsize=(7, 5))
        bars = plt.bar(labels, values, color=['#ff6b6b', '#ffd93d', '#6bcf7f', '#4ecdc4', '#45b7d1'])
        plt.xlabel('分数段', fontsize=11)
        plt.ylabel('人数', fontsize=11)
        plt.title(f'{stats.get("course_name", "课程")} - 分数段分布', fontsize=13, fontweight='bold')
        plt.grid(axis='y', alpha=0.3)

        # 在柱状图上显示数值
        for bar, value in zip(bars, values):
            if value > 0:
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                        str(value), ha='center', va='bottom', fontsize=10)

        plt.tight_layout()

        # 转换为图片
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        pix = QPixmap()
        pix.loadFromData(buf.read())
        self.chart_label.setPixmap(pix)
        plt.close()

