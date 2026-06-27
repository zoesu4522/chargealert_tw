import os
import requests

TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"


def get_tdx_token():
    """向 TDX 取 OAuth2 token。webhook 服務用環境變數讀金鑰(無 config.py)。"""
    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("TDX_CLIENT_ID"),
        "client_secret": os.getenv("TDX_CLIENT_SECRET"),
    }
    try:
        print(" 正在向 TDX 申請通行證...")
        resp = requests.post(TDX_AUTH_URL, data=data, timeout=10)
        resp.raise_for_status()
        token = resp.json().get("access_token")
        print(" 成功拿到通行證!")
        return token
    except requests.exceptions.RequestException as e:
        print(f" 申請通行證失敗:{e}")
        return None

#兩個服務是各自獨立的容器,各自帶自己的 TDX 取 token 工具,不共用 config