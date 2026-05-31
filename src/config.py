import os
from dotenv import load_dotenv

load_dotenv()

#API
TDX_CLIENT_ID = os.getenv("TDX_CLIENT_ID")
TDX_CLIENT_SECRET = os.getenv("TDX_CLIENT_SECRET")

#認證網址
TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"

#API 網址
TDX_API_BASE = "https://tdx.transportdata.tw/api/basic"

#充電站 API 

#充電樁即時狀態
EV_LIVE_STATUS_PATH = "/v1/EV/ConnectorLiveStatus/City"
#充電樁基本資料
EV_CONNECTOR_PATH = "/v1/EV/Connector/City"

#預設抓取桃園
TARGET_CITY = "Taoyuan"

#MySQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "chargealert")

#LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
LINE_NOTIFY_ENABLED = os.getenv("LINE_NOTIFY_ENABLED", "true").lower() == "true"

def check_config():
    missing = []
    if not TDX_CLIENT_ID:
        missing.append("TDX_CLIENT_ID")
    if not TDX_CLIENT_SECRET:
        missing.append("TDX_CLIENT_SECRET")

    if missing:
        print("  以下設定沒填,請檢查 .env 檔:")
        for m in missing:
            print(f"   - {m}")
        return False
    return True