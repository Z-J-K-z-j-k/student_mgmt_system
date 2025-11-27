# client/pages/crawl_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt
from ..utils.api_client import APIClient

class CrawlPage(QWidget):
    def __init__(self, api: APIClient):
        super().__init__()
        self.api = api

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # 标题
        title = QLabel("🕷️ 数据爬虫管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f;")
        layout.addWidget(title)

        # 说明
        info = QLabel("此功能用于从外部数据源爬取数据并导入系统。")
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        # 爬虫操作区域
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)

        # 爬取教师数据
        self.btn_crawl_teachers = QPushButton("爬取北邮计算机学院教师数据")
        self.btn_crawl_teachers.setStyleSheet("""
            QPushButton {
                background-color: #3a8dd0;
                color: white;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5BA0FF;
            }
        """)
        self.btn_crawl_teachers.clicked.connect(self.crawl_teachers)
        btn_layout.addWidget(self.btn_crawl_teachers)

        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("爬虫操作日志将显示在这里...")
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("操作日志："))
        layout.addWidget(self.log_text)

        layout.addStretch()

    def log(self, message: str):
        """添加日志"""
        self.log_text.append(f"[{self._get_timestamp()}] {message}")

    def _get_timestamp(self):
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def crawl_teachers(self):
        """爬取北邮教师数据"""
        reply = QMessageBox.question(
            self,
            "确认",
            "是否要爬取北京邮电大学计算机学院的教师数据？\n这可能需要一些时间。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.log("开始爬取北邮计算机学院教师数据...")
        self.btn_crawl_teachers.setEnabled(False)

        try:
            resp = self.api.post("/api/crawler/teachers/bupt")
            data = resp.json()

            if data.get("status") == "ok":
                msg = data.get("message", "爬取完成")
                if data.get("warning"):
                    msg += f"\n警告：{data['warning']}"
                self.log(f"✅ 成功：{msg}")
                QMessageBox.information(self, "成功", msg)
            else:
                error_msg = data.get("msg", "爬取失败")
                self.log(f"❌ 失败：{error_msg}")
                QMessageBox.warning(self, "失败", error_msg)
        except Exception as e:
            error_msg = f"爬取失败：{e}"
            self.log(f"❌ 错误：{error_msg}")
            QMessageBox.critical(self, "错误", error_msg)
        finally:
            self.btn_crawl_teachers.setEnabled(True)

