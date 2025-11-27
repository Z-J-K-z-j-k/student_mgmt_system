# client/pages/comprehensive_stats_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
import requests
from ..utils.api_client import APIClient, SERVER_URL


class ComprehensiveStatsPage(QWidget):
    """综合统计页面 - 只包含按专业统计和按年级统计两个图表"""
    
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题和刷新按钮
        header = QHBoxLayout()
        title = QLabel("📊 综合统计")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1f1f1f;")
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
        btn_refresh.clicked.connect(self.load_data)
        header.addWidget(btn_refresh)
        layout.addLayout(header)
        
        # 图表区域（上下布局）
        charts_layout = QVBoxLayout()
        charts_layout.setSpacing(20)
        
        # 1. 按专业统计（柱状图）
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
        
        major_title = QLabel("📊 按专业统计（柱状图）")
        major_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        major_title.setWordWrap(False)
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
        
        # 专业统计文字说明
        self.major_stats_label = QLabel("")
        self.major_stats_label.setTextFormat(Qt.TextFormat.RichText)  # 启用HTML格式
        self.major_stats_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 13px;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 4px;
                margin-top: 10px;
            }
        """)
        self.major_stats_label.setWordWrap(True)
        self.major_stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        major_layout.addWidget(self.major_stats_label)
        
        charts_layout.addWidget(major_frame)
        
        # 2. 按年级统计（折线图）
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
        
        grade_title = QLabel("📈 按年级统计（折线图）")
        grade_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f1f1f; margin-bottom: 10px;")
        grade_title.setWordWrap(False)
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
        
        # 年级统计文字说明
        self.grade_stats_label = QLabel("")
        self.grade_stats_label.setTextFormat(Qt.TextFormat.RichText)  # 启用HTML格式
        self.grade_stats_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 13px;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 4px;
                margin-top: 10px;
            }
        """)
        self.grade_stats_label.setWordWrap(True)
        self.grade_stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grade_layout.addWidget(self.grade_stats_label)
        
        charts_layout.addWidget(grade_frame)
        
        layout.addLayout(charts_layout)
        layout.addStretch()
        
        # 初始加载数据
        self.load_data()
    
    def load_data(self):
        """加载专业和年级统计数据"""
        # 加载专业图表和统计数据
        try:
            url = f"{SERVER_URL}/api/charts/major_avg_bar.png"
            resp = requests.get(url, timeout=10, headers=self.api._headers())
            if resp.status_code == 200:
                pix = QPixmap()
                if pix.loadFromData(resp.content):
                    self.major_chart.setPixmap(
                        pix.scaled(800, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    )
                else:
                    self.major_chart.setText(f"专业图表解析失败\n响应长度: {len(resp.content)} 字节")
            else:
                error_msg = f"HTTP {resp.status_code}"
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", error_msg)
                except:
                    pass
                self.major_chart.setText(f"专业图表加载失败\n{error_msg}")
        except Exception as e:
            import traceback
            error_detail = str(e)
            self.major_chart.setText(f"专业图表加载异常\n{error_detail}")
            print(f"加载专业图表失败: {traceback.format_exc()}")
        
        # 加载专业统计数据
        try:
            resp = self.api.get("/api/stats/major")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    stats = data.get("data", [])
                    self.update_major_stats_text(stats)
                else:
                    error_msg = data.get("msg", "未知错误")
                    self.major_stats_label.setText(f"<b>📊 专业统计说明：</b><br>加载失败：{error_msg}")
            else:
                self.major_stats_label.setText(f"<b>📊 专业统计说明：</b><br>HTTP {resp.status_code} 错误")
        except Exception as e:
            import traceback
            print(f"加载专业统计数据失败: {traceback.format_exc()}")
            self.major_stats_label.setText(f"<b>📊 专业统计说明：</b><br>加载异常：{str(e)}")
        
        # 加载年级图表和统计数据
        try:
            url = f"{SERVER_URL}/api/charts/grade_trend.png"
            resp = requests.get(url, timeout=10, headers=self.api._headers())
            if resp.status_code == 200:
                pix = QPixmap()
                if pix.loadFromData(resp.content):
                    self.grade_chart.setPixmap(
                        pix.scaled(800, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    )
                else:
                    self.grade_chart.setText(f"年级图表解析失败\n响应长度: {len(resp.content)} 字节")
            else:
                error_msg = f"HTTP {resp.status_code}"
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("msg", error_msg)
                except:
                    pass
                self.grade_chart.setText(f"年级图表加载失败\n{error_msg}")
        except Exception as e:
            import traceback
            error_detail = str(e)
            self.grade_chart.setText(f"年级图表加载异常\n{error_detail}")
            print(f"加载年级图表失败: {traceback.format_exc()}")
        
        # 加载年级统计数据
        try:
            resp = self.api.get("/api/stats/grade")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    stats = data.get("data", [])
                    self.update_grade_stats_text(stats)
                else:
                    error_msg = data.get("msg", "未知错误")
                    self.grade_stats_label.setText(f"<b>📈 年级统计说明：</b><br>加载失败：{error_msg}")
            else:
                self.grade_stats_label.setText(f"<b>📈 年级统计说明：</b><br>HTTP {resp.status_code} 错误")
        except Exception as e:
            import traceback
            print(f"加载年级统计数据失败: {traceback.format_exc()}")
            self.grade_stats_label.setText(f"<b>📈 年级统计说明：</b><br>加载异常：{str(e)}")
    
    def update_major_stats_text(self, stats):
        """更新专业统计文字说明"""
        if not stats:
            self.major_stats_label.setText("暂无专业统计数据")
            return
        
        lines = ["<b>📊 专业统计说明：</b>"]
        for stat in stats:
            major = stat.get("major", "未知专业")
            avg_score = stat.get("avg_score")
            student_count = stat.get("student_count", 0)
            total_scores = stat.get("total_scores", 0)
            pass_rate = stat.get("pass_rate", 0)
            
            if avg_score is not None:
                lines.append(
                    f"• <b>{major}</b>：平均分 <b>{avg_score:.2f}分</b>，"
                    f"学生数 {student_count}人，成绩记录 {total_scores}条，及格率 {pass_rate:.1f}%"
                )
            else:
                lines.append(
                    f"• <b>{major}</b>：暂无成绩数据，学生数 {student_count}人"
                )
        
        self.major_stats_label.setText("<br>".join(lines))
    
    def update_grade_stats_text(self, stats):
        """更新年级统计文字说明"""
        if not stats:
            self.grade_stats_label.setText("暂无年级统计数据")
            return
        
        grade_names = {1: "大一", 2: "大二", 3: "大三", 4: "大四"}
        lines = ["<b>📈 年级统计说明：</b>"]
        for stat in stats:
            grade = stat.get("grade")
            if grade is None:
                continue
            grade_name = grade_names.get(grade, f"{grade}年级")
            avg_score = stat.get("avg_score")
            student_count = stat.get("student_count", 0)
            total_scores = stat.get("total_scores", 0)
            pass_rate = stat.get("pass_rate", 0)
            
            if avg_score is not None:
                lines.append(
                    f"• <b>{grade_name}</b>：平均分 <b>{avg_score:.2f}分</b>，"
                    f"学生数 {student_count}人，成绩记录 {total_scores}条，及格率 {pass_rate:.1f}%"
                )
            else:
                lines.append(
                    f"• <b>{grade_name}</b>：暂无成绩数据，学生数 {student_count}人"
                )
        
        self.grade_stats_label.setText("<br>".join(lines))

