# client/utils/api_client.py
import requests

SERVER_URL = "http://127.0.0.1:5000"   # 另一台机器时改成服务器 IP

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

    def get(self, path, **kwargs):
        return requests.get(SERVER_URL + path, headers=self._headers(), timeout=5, **kwargs)

    def post(self, path, json=None, **kwargs):
        return requests.post(SERVER_URL + path, json=json, headers=self._headers(), timeout=5, **kwargs)

    def put(self, path, json=None, **kwargs):
        return requests.put(SERVER_URL + path, json=json, headers=self._headers(), timeout=5, **kwargs)

    def delete(self, path, **kwargs):
        return requests.delete(SERVER_URL + path, headers=self._headers(), timeout=5, **kwargs)

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
