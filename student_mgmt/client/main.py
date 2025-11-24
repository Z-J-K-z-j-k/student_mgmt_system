# client/main.py
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
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
    main_win = MainWindow(api)

    def on_login_success():
        login_win.close()
        main_win.lbl_user.setText(f"当前用户：{api.real_name}（{api.role}）")
        main_win.show()

    login_win = LoginWindow(api, on_login_success)
    login_win.show()


    login_win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
