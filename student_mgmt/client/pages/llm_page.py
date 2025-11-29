# client/pages/llm_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel, 
    QHBoxLayout, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QKeyEvent
import importlib
from datetime import datetime

markdown_module = None
try:
    markdown_module = importlib.import_module("markdown")
    render_markdown = markdown_module.markdown
except ImportError:  # pragma: no cover
    def render_markdown(text, extensions=None):
        return text.replace("\n", "<br>")

from ..utils.api_client import APIClient


class ChatTextEdit(QTextEdit):
    """支持Enter发送、Shift+Enter换行的输入框"""
    send_requested = pyqtSignal()
    
    def keyPressEvent(self, event: QKeyEvent):
        """处理按键事件"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # 如果按下了Shift，则换行
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                # 否则发送消息
                self.send_requested.emit()
        else:
            super().keyPressEvent(event)


class LLMWorker(QThread):
    success = pyqtSignal(str)
    failure = pyqtSignal(str)

    def __init__(self, api: APIClient, prompt: str, parent=None):
        super().__init__(parent)
        self.api = api
        self.prompt = prompt

    def run(self):
        try:
            # LLM请求需要更长的超时时间（60秒）
            resp = self.api.post("/api/llm_chat", json={"prompt": self.prompt}, timeout=60)
            if resp.status_code >= 400:
                try:
                    message = resp.json().get("msg", "服务器返回错误")
                except Exception:
                    message = resp.text or "服务器返回错误"
                raise ValueError(message)
            data = resp.json()
            if data.get("status") != "ok":
                raise ValueError(data.get("msg", "调用失败"))
            reply = data.get("reply", "（没有收到回复）")
            self.success.emit(reply)
        except Exception as exc:
            self.failure.emit(str(exc))


class MessageBubble(QFrame):
    """消息气泡组件"""
    def __init__(self, text: str, is_user: bool = True, is_markdown: bool = False, timestamp: str = None, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setup_ui(text, is_markdown, timestamp)
        
    def setup_ui(self, text: str, is_markdown: bool, timestamp: str):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        # 外层容器，用于对齐
        container = QHBoxLayout()
        container.setContentsMargins(12, 8, 12, 8)
        container.setSpacing(8)
        
        if not self.is_user:
            # 助手消息：头像在左，消息在右
            avatar_label = QLabel("🤖")
            avatar_label.setFixedSize(36, 36)
            avatar_label.setStyleSheet("""
                QLabel {
                    background-color: #f0f0f0;
                    border-radius: 18px;
                    font-size: 20px;
                    text-align: center;
                }
            """)
            avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container.addWidget(avatar_label)
            
        # 消息内容区域
        content_widget = QFrame()
        content_widget.setFrameShape(QFrame.Shape.NoFrame)
        content_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        
        if self.is_user:
            # 用户消息：蓝色背景，靠右
            content_widget.setStyleSheet("""
                QFrame {
                    background-color: #3a8dd0;
                    border-radius: 12px;
                    padding: 10px 14px;
                }
            """)
            container.addStretch()
        else:
            # 助手消息：灰色背景，靠左
            content_widget.setStyleSheet("""
                QFrame {
                    background-color: #f5f5f5;
                    border-radius: 12px;
                    padding: 10px 14px;
                }
            """)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        
        # 消息文本
        text_label = QLabel()
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        # 设置最大宽度，确保消息不会太宽（约600px）
        text_label.setMaximumWidth(600)
        
        if is_markdown:
            html = render_markdown(text, extensions=["extra"])
            # 美化markdown样式
            html = f"""
            <style>
                body {{ margin: 0; padding: 0; }}
                p {{ margin: 4px 0; }}
                code {{ background-color: rgba(0,0,0,0.1); padding: 2px 6px; border-radius: 4px; font-family: 'Consolas', monospace; }}
                pre {{ background-color: rgba(0,0,0,0.1); padding: 8px; border-radius: 6px; overflow-x: auto; }}
                pre code {{ background-color: transparent; padding: 0; }}
                ul, ol {{ margin: 4px 0; padding-left: 20px; }}
                li {{ margin: 2px 0; }}
                h1, h2, h3, h4, h5, h6 {{ margin: 8px 0 4px 0; }}
            </style>
            <body>{html}</body>
            """
            text_label.setText(html)
        else:
            # 转义HTML并保留换行
            safe = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            text_label.setText(safe)
        
        if self.is_user:
            text_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-size: 15px;
                    line-height: 1.5;
                    background-color: transparent;
                }
            """)
        else:
            text_label.setStyleSheet("""
                QLabel {
                    color: #333333;
                    font-size: 15px;
                    line-height: 1.5;
                    background-color: transparent;
                }
            """)
        
        content_layout.addWidget(text_label)
        
        # 时间戳
        if timestamp:
            time_label = QLabel(timestamp)
            if self.is_user:
                # 用户消息中的时间戳：白色半透明
                time_label.setStyleSheet("""
                    QLabel {
                        color: rgba(255, 255, 255, 0.7);
                        font-size: 11px;
                        background-color: transparent;
                    }
                """)
            else:
                # 助手消息中的时间戳：灰色
                time_label.setStyleSheet("""
                    QLabel {
                        color: #999999;
                        font-size: 11px;
                        background-color: transparent;
                    }
                """)
            content_layout.addWidget(time_label)
        
        container.addWidget(content_widget)
        
        if self.is_user:
            # 用户消息：头像在右
            avatar_label = QLabel("👤")
            avatar_label.setFixedSize(36, 36)
            avatar_label.setStyleSheet("""
                QLabel {
                    background-color: #e3f2fd;
                    border-radius: 18px;
                    font-size: 20px;
                    text-align: center;
                }
            """)
            avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container.addWidget(avatar_label)
        else:
            container.addStretch()
        
        main_layout.addLayout(container)
        
        # 设置整体样式
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)


class LoadingBubble(QFrame):
    """加载动画气泡"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.start_animation()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # 头像
        avatar_label = QLabel("🤖")
        avatar_label.setFixedSize(36, 36)
        avatar_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border-radius: 18px;
                font-size: 20px;
                text-align: center;
            }
        """)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(avatar_label)
        
        # 加载动画容器
        loading_widget = QFrame()
        loading_widget.setFrameShape(QFrame.Shape.NoFrame)
        loading_widget.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 12px;
                padding: 12px 16px;
            }
        """)
        loading_layout = QHBoxLayout(loading_widget)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(6)
        
        # 三个点动画
        self.dots = []
        for i in range(3):
            dot = QLabel("●")
            dot.setStyleSheet("""
                QLabel {
                    color: #999999;
                    font-size: 12px;
                    background-color: transparent;
                }
            """)
            self.dots.append(dot)
            loading_layout.addWidget(dot)
        
        loading_layout.addStretch()
        layout.addWidget(loading_widget)
        layout.addStretch()
        
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
    
    def start_animation(self):
        """启动加载动画"""
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_dots)
        self.animation_timer.start(500)  # 每500ms更新一次
        self.dot_index = 0
    
    def update_dots(self):
        """更新动画点"""
        for i, dot in enumerate(self.dots):
            if i == self.dot_index:
                dot.setStyleSheet("""
                    QLabel {
                        color: #666666;
                        font-size: 14px;
                        background-color: transparent;
                    }
                """)
            else:
                dot.setStyleSheet("""
                    QLabel {
                        color: #cccccc;
                        font-size: 12px;
                        background-color: transparent;
                    }
                """)
        self.dot_index = (self.dot_index + 1) % 3
    
    def stop_animation(self):
        """停止动画"""
        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()


class LLMPage(QWidget):
    def __init__(self, api: APIClient, role: str = "student"):
        super().__init__()
        self.api = api
        self.role = role
        self.worker = None
        self.loading_bubble = None
        self.message_widgets = []  # 保存所有消息widget，用于清理
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 根据角色显示不同的标题
        if role == "admin":
            title = "🤖 系统管理助手（基于全数据库信息）"
            placeholder = "请在这里输入你的问题，例如：\n当前学生成绩分布情况如何？\n哪个专业的平均GPA最高？\n哪些课程需要重点关注？"
        elif role == "teacher":
            title = "👨‍🏫 教学管理助手（大模型接口）"
            placeholder = "请在这里输入你的问题，例如：\n我的课程学生成绩如何？\n如何提高课程通过率？"
        else:
            title = "💡 学习规划 / 选课咨询助手（大模型接口）"
            placeholder = "请在这里输入你的问题，例如：\n我数学 60 分、英语 90 分，该怎么安排复习？"

        # 标题
        self.lbl_info = QLabel(title)
        self.lbl_info.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #1f1f1f;
                padding: 8px 0;
                background-color: transparent;
            }
        """)
        layout.addWidget(self.lbl_info)

        # 消息列表区域（使用ScrollArea）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        
        # 消息容器
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.setSpacing(4)
        self.messages_layout.addStretch()  # 顶部弹性空间，让消息从底部开始
        
        scroll_area.setWidget(self.messages_container)
        layout.addWidget(scroll_area, 1)  # 占据剩余空间
        
        self.scroll_area = scroll_area

        # 输入区域
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.Shape.NoFrame)
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(8)
        
        # 输入框（支持Enter发送）
        self.text_input = ChatTextEdit()
        self.text_input.setPlaceholderText(placeholder)
        self.text_input.setFixedHeight(100)
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 10px;
                font-size: 15px;
                line-height: 1.5;
                color: #1f1f1f;
            }
            QTextEdit:focus {
                border: 1px solid #3a8dd0;
            }
        """)
        self.text_input.send_requested.connect(self.send_msg)
        input_layout.addWidget(self.text_input)
        
        # 控制按钮区域
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 13px;
                background-color: transparent;
            }
        """)
        self.lbl_status.hide()
        controls_layout.addWidget(self.lbl_status)
        controls_layout.addStretch()

        self.btn_send = QPushButton("发送")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #3a8dd0;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 15px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5BA0FF;
            }
            QPushButton:pressed {
                background-color: #2F74D0;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.btn_send.clicked.connect(self.send_msg)
        controls_layout.addWidget(self.btn_send)
        
        input_layout.addLayout(controls_layout)
        layout.addWidget(input_frame)

        # 加载历史记录
        self.load_history()

    def add_message(self, text: str, is_user: bool = True, is_markdown: bool = False, timestamp: str = None):
        """添加消息气泡"""
        # 移除加载动画
        if self.loading_bubble:
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.stop_animation()
            self.loading_bubble.deleteLater()
            self.loading_bubble = None
        
        # 创建消息气泡
        bubble = MessageBubble(text, is_user, is_markdown, timestamp, self)
        self.message_widgets.append(bubble)
        
        # 插入到stretch之前
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        
        # 滚动到底部
        QTimer.singleShot(50, self.scroll_to_bottom)
    
    def add_loading_bubble(self):
        """添加加载动画"""
        if self.loading_bubble:
            return
        
        self.loading_bubble = LoadingBubble(self)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, self.loading_bubble)
        QTimer.singleShot(50, self.scroll_to_bottom)
    
    def scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def set_busy(self, busy: bool):
        """设置忙碌状态"""
        self.btn_send.setEnabled(not busy)
        if busy:
            self.lbl_status.setText("正在思考…")
            self.lbl_status.show()
            self.add_loading_bubble()
        else:
            self.lbl_status.hide()
            self.lbl_status.clear()
            if self.loading_bubble:
                self.messages_layout.removeWidget(self.loading_bubble)
                self.loading_bubble.stop_animation()
                self.loading_bubble.deleteLater()
                self.loading_bubble = None

    def send_msg(self):
        """发送消息"""
        prompt = self.text_input.toPlainText().strip()
        if not prompt:
            return
        
        # 添加用户消息
        timestamp = datetime.now().strftime("%H:%M")
        self.add_message(prompt, is_user=True, timestamp=timestamp)
        
        # 清空输入框
        self.text_input.clear()
        self.set_busy(True)

        # 启动工作线程
        self.worker = LLMWorker(self.api, prompt, self)
        self.worker.success.connect(self.handle_success)
        self.worker.failure.connect(self.handle_failure)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def handle_success(self, reply: str):
        """处理成功响应"""
        timestamp = datetime.now().strftime("%H:%M")
        self.add_message(reply, is_user=False, is_markdown=True, timestamp=timestamp)

    def handle_failure(self, err: str):
        """处理失败响应"""
        timestamp = datetime.now().strftime("%H:%M")
        self.add_message(f"❌ 请求失败：{err}", is_user=False, timestamp=timestamp)

    def on_worker_finished(self):
        """工作线程完成"""
        self.set_busy(False)
        self.worker = None

    def load_history(self):
        """加载历史记录"""
        try:
            resp = self.api.get("/api/llm_logs", params={"limit": 20})
            data = resp.json()
            if data.get("status") != "ok":
                self.add_message(data.get("msg", "无法获取历史记录"), is_user=False)
                return
            
            logs = data.get("data", [])
            if not logs:
                # 显示欢迎消息
                welcome_msg = "👋 你好！我是你的智能助手，有什么问题尽管问我吧～"
                self.add_message(welcome_msg, is_user=False)
                return
            
            # 加载历史消息
            for item in reversed(logs):
                ts = item.get("created_at", "")
                query = item.get("query_text", "")
                reply = item.get("response_summary", "")
                
                # 提取时间（如果有）
                timestamp = None
                if ts:
                    try:
                        # 尝试解析时间戳
                        if " " in ts:
                            timestamp = ts.split(" ")[1][:5]  # 提取 HH:MM
                    except:
                        pass
                
                if query:
                    self.add_message(query, is_user=True, timestamp=timestamp)
                if reply:
                    self.add_message(reply, is_user=False, is_markdown=True, timestamp=timestamp)
            
            # 滚动到底部
            QTimer.singleShot(100, self.scroll_to_bottom)
        except Exception as e:
            # 历史记录失败时显示欢迎消息
            welcome_msg = "👋 你好！我是你的智能助手，有什么问题尽管问我吧～"
            self.add_message(welcome_msg, is_user=False)
