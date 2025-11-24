# client/pages/stats_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import requests
from ..utils.api_client import APIClient, SERVER_URL

class StatsPage(QWidget):
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api

        layout = QVBoxLayout(self)

        self.lbl_overview = QLabel("统计信息：")
        self.lbl_overview.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.lbl_overview)

        btn_box = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新统计")
        self.btn_refresh.clicked.connect(self.refresh_stats)
        btn_box.addWidget(self.btn_refresh)
        layout.addLayout(btn_box)

        # 图表
        self.lbl_hist = QLabel()
        self.lbl_hist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pie = QLabel()
        self.lbl_pie.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_hist)
        layout.addWidget(self.lbl_pie)

        self.refresh_stats()
        self.load_charts()

    def refresh_stats(self):
        resp = self.api.get("/api/stats/overview")
        data = resp.json().get("data", {})
        text = (
            f"总成绩记录：{data.get('total_records', 0)} 条\n"
            f"平均分：{data.get('avg_score', 'N/A')}\n"
            f"及格率：{data.get('pass_rate', 0)*100:.1f}%\n"
            f"优秀率：{data.get('excellent_rate', 0)*100:.1f}%\n"
            f"按专业平均分：{data.get('avg_by_major', {})}\n"
            f"按班级平均分：{data.get('avg_by_class', {})}\n"
        )
        self.lbl_overview.setText(text)

    def load_charts(self):
        # 从服务器直接拉图片
        for chart_name, label in [
            ("score_hist.png", self.lbl_hist),
            ("major_pie.png", self.lbl_pie),
        ]:
            url = f"{SERVER_URL}/api/charts/{chart_name}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                pix = QPixmap()
                pix.loadFromData(resp.content)
                label.setPixmap(pix)
