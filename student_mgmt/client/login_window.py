"""
Legacy import shim so that existing code can keep doing:

    from .login_window import LoginWindow

while the actual implementation lives in utils.login_window.
"""

from .utils.login_window import LoginWindow  # noqa: F401
