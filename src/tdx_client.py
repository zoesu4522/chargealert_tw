import requests
import config


def get_tdx_token():
    #準備要送給 TDX 的資料
    data = {
        "grant_type": "client_credentials",
        "client_id": config.TDX_CLIENT_ID,
        "client_secret": config.TDX_CLIENT_SECRET,
    }

    try:
        #發送請求
        print(" 正在向 TDX 申請通行證...")
        response = requests.post(config.TDX_AUTH_URL, data=data, timeout=10)
        response.raise_for_status()  # 如果失敗(例如金鑰錯)會在這裡報錯

        #response中取出 token
        token = response.json().get("access_token")
        print(" 成功拿到通行證!")
        return token

    except requests.exceptions.RequestException as e:
        print(f" 申請通行證失敗:{e}")
        return None


#測試
if __name__ == "__main__":
    if not config.check_config():
        print("請先在 .env 填好 TDX 金鑰再執行")
    else:
        token = get_tdx_token()
        if token:
            #只印前後幾個字,避免完整token外洩
            print(f" 通行證(前20字):{token[:20]}...")
            print(f"   通行證長度:{len(token)} 字元")
            print("\n 太好了!你的 TDX 金鑰可以用,認證成功!")
#兩個服務是各自獨立的容器,各自帶自己的 TDX 取 token 工具,不共用 config