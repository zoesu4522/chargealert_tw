import requests
import config


def get_tdx_token():
    """
    用 client_id + client_secret 向 TDX 換取 access token
    回傳 token 字串,失敗則回傳 None
    """
    # 準備要送給 TDX 的資料(就像填一張換證申請表)
    data = {
        "grant_type": "client_credentials",
        "client_id": config.TDX_CLIENT_ID,
        "client_secret": config.TDX_CLIENT_SECRET,
    }

    try:
        # 向 TDX 的認證網址發送請求
        print("🔑 正在向 TDX 申請通行證...")
        response = requests.post(config.TDX_AUTH_URL, data=data, timeout=10)
        response.raise_for_status()  # 如果失敗(例如金鑰錯)會在這裡報錯

        # 從回應中取出 token
        token = response.json().get("access_token")
        print(" 成功拿到通行證!")
        return token

    except requests.exceptions.RequestException as e:
        print(f" 申請通行證失敗:{e}")
        return None


# ===== 測試:直接執行這支程式時,試著拿 token =====
if __name__ == "__main__":
    # 先檢查設定有沒有填好
    if not config.check_config():
        print("請先在 .env 填好 TDX 金鑰再執行")
    else:
        token = get_tdx_token()
        if token:
            # 只印前後幾個字,避免完整 token 外洩
            print(f" 通行證(前20字):{token[:20]}...")
            print(f"   通行證長度:{len(token)} 字元")
            print("\n 太好了!你的 TDX 金鑰可以用,認證成功!")