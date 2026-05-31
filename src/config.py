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


# 縣市設定(多縣市架構)
# 設計重點:擴充彈性放在「資料設定」,不寫死在邏輯裡。
#
#   ACTIVE_CITIES → 排程「主動」定時抓取 + 推播的縣市。每多一個約 +1.9 點/月。
#   QUERY_CITIES  → 使用者按按鈕時才「按需(On-Demand)」即時抓,平時不耗點。
#
# 目前策略:維持 TDX 免費額度(3 點/月),只桃園主動推播,其他全按需。
# 之後若升級 TDX 銅級(200 點/月),只要把縣市名從 QUERY_CITIES
# 搬到 ACTIVE_CITIES,排程自動擴增,邏輯一行都不用改。

#主動推播(排程定時抓):目前只桃園
ACTIVE_CITIES = ["Taoyuan"]

#按需查詢(使用者點選才抓):7 大都會 + 其他 15 縣市
QUERY_CITIES = [
    "Taipei", "NewTaipei", "HsinchuCity",
    "Taichung", "Tainan", "Kaohsiung",
    #其他 15 個縣市(On-Demand,平時不耗點)
    "Keelung", "HsinchuCounty", "MiaoliCounty", "ChanghuaCounty",
    "NantouCounty", "YunlinCounty", "ChiayiCity", "ChiayiCounty",
    "PingtungCounty", "YilanCounty", "HualienCounty", "TaitungCounty",
    "PenghuCounty", "KinmenCounty", "LienchiangCounty",
]

#全部支援的縣市(主動 + 按需)
ALL_CITIES = ACTIVE_CITIES + QUERY_CITIES

#向後相容:既有程式(scheduler.py 等)仍可引用 TARGET_CITY。
#永遠指向第一個主動推播縣市,語意等同「主力縣市」。
TARGET_CITY = ACTIVE_CITIES[0]

#縣市名對照表:LINE Postback 用英文 city code,CWA 天氣 API 用中文(注意「臺」非「台」)。
#中文名同時也是 TDX City 路徑參數可接受的識別之外的顯示用途。
CITY_NAME_MAP = {
    "Taipei": "臺北市",
    "NewTaipei": "新北市",
    "Taoyuan": "桃園市",
    "Taichung": "臺中市",
    "Tainan": "臺南市",
    "Kaohsiung": "高雄市",
    "Keelung": "基隆市",
    "HsinchuCity": "新竹市",
    "HsinchuCounty": "新竹縣",
    "MiaoliCounty": "苗栗縣",
    "ChanghuaCounty": "彰化縣",
    "NantouCounty": "南投縣",
    "YunlinCounty": "雲林縣",
    "ChiayiCity": "嘉義市",
    "ChiayiCounty": "嘉義縣",
    "PingtungCounty": "屏東縣",
    "YilanCounty": "宜蘭縣",
    "HualienCounty": "花蓮縣",
    "TaitungCounty": "臺東縣",
    "PenghuCounty": "澎湖縣",
    "KinmenCounty": "金門縣",
    "LienchiangCounty": "連江縣",
}


def city_zh(city: str) -> str:
    """英文 city code 轉中文名;查不到就回原字串,不會炸。"""
    return CITY_NAME_MAP.get(city, city)


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