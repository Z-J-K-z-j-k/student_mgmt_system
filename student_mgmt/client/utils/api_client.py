# client/utils/api_client.py
import requests

# 从配置文件导入服务器地址
try:
    from ..config import SERVER_URL
except ImportError:
    # 如果配置文件不存在，使用默认值
    SERVER_URL = "http://127.0.0.1:5000"

class APIClient:
    def __init__(self):
        self.token = None
        self.user_id = None
        self.role = None
        self.real_name = None

    # ---------- 通用 ----------

    def _headers(self):
        # 这里简单一点，没做真正 token 校验
        return {"X-Token": self.token} if self.token else {}

    def _timeout(self, kwargs):
        return kwargs.pop("timeout", 20)

    def get(self, path, **kwargs):
        return requests.get(
            SERVER_URL + path,
            headers=self._headers(),
            timeout=self._timeout(kwargs),
            **kwargs,
        )

    def post(self, path, json=None, **kwargs):
        return requests.post(
            SERVER_URL + path,
            json=json,
            headers=self._headers(),
            timeout=self._timeout(kwargs),
            **kwargs,
        )

    def put(self, path, json=None, **kwargs):
        return requests.put(
            SERVER_URL + path,
            json=json,
            headers=self._headers(),
            timeout=self._timeout(kwargs),
            **kwargs,
        )

    def delete(self, path, **kwargs):
        return requests.delete(
            SERVER_URL + path,
            headers=self._headers(),
            timeout=self._timeout(kwargs),
            **kwargs,
        )

    # ---------- 业务 ----------

    def login(self, username, password, role):
        resp = self.post("/api/login", json={
            "username": username,
            "password": password,
            "role": role
        })
        data = resp.json()
        if data.get("status") == "ok":
            self.token = data["token"]
            self.user_id = data["user_id"]
            self.role = data["role"]
            self.real_name = data["real_name"]
        return data
