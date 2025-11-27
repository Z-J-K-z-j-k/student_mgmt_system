# client/main.py
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# 兼容直接运行脚本（python student_mgmt/client/main.py）
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from client.utils.api_client import APIClient
    from client.login_window import LoginWindow
    from client.main_window import MainWindow
else:
    from .utils.api_client import APIClient
    from .login_window import LoginWindow
    from .main_window import MainWindow

def load_qss(app):
    qss_path = Path(__file__).parent / "resources" / "style.qss"
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

def main():
    app = QApplication(sys.argv)
    load_qss(app)

    api = APIClient()
    # 只加载登录窗口，登录成功后由login_window根据角色打开对应的主界面
    login_win = LoginWindow(api, None)
    login_win.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
