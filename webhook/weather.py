"""
weather.py — ChargeAlert TW 天氣整合(Phase 5.5 Weather Advisor)

資料來源:中央氣象署 CWA 開放資料平台
  資料集 F-C0032-001(一般天氣預報-今明 36 小時天氣預報,縣市層級)
  base URL:https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001
  線上文件:https://opendata.cwa.gov.tw/dist/opendata-swagger.html

設計重點:
  1. 只用 Python 標準函式庫(urllib),不增加任何套件依賴 → t3.micro 友善,
     webhook/requirements.txt 不用改。
  2. 內建 30 分鐘記憶體快取,避免每次請求都打 CWA(預報本來一天只更新幾次)。
  3. 天氣建議(advisory)走「規則判斷」,不經 LLM → 結果穩定不會幻覺,
     也完全不依賴 Bedrock 配額,跟專案「事實層與自然語言層分離」的精神一致。
  4. 外部 API 掛掉時 graceful fallback:有舊快取就回舊資料,沒有就回 ok=False,
     不會讓 /api/weather 噴 500。
  5. 所有環境變數都在「函式內」即時讀取,不在模組載入時讀。這樣不管 main.py 的
     load_dotenv() 在 import weather 之前或之後跑,實際呼叫時都拿得到值,
     避免 import 順序造成 CWA_API_KEY 抓到空字串。
"""

import os
import ssl
import json
import time
import threading
import urllib.parse
import urllib.request

# ---- 固定設定(與環境變數無關,可放模組層) ----
DATASET = "F-C0032-001"
BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/" + DATASET
HTTP_TIMEOUT = 8  # 對外請求逾時秒數

# ---- 記憶體快取(多執行緒安全) ----
_cache = {"data": None, "ts": 0.0}
_lock = threading.Lock()


def _build_advisory(pop, wx):
    """依降雨機率 PoP(%) 與天氣現象文字,產生給充電使用者的白話建議。純規則,不經 LLM。"""
    try:
        pop_val = int(pop)
    except (TypeError, ValueError):
        pop_val = -1

    if pop_val >= 70:
        return "降雨機率偏高,前往充電站請注意路況並攜帶雨具,插拔槍時留意手部與接頭保持乾燥。"
    if pop_val >= 30:
        return "可能有短暫降雨,出門充電建議留意天氣變化。"
    if pop_val >= 0:
        return "天氣大致穩定,適合外出充電。"
    return f"目前天氣:{wx or '資料更新中'}。"


def _to_int(s):
    """把 CWA 回傳的字串數字安全轉成 int,失敗回 None(支援負溫度)。"""
    if s is None:
        return None
    s = str(s).strip()
    return int(s) if s.lstrip("-").isdigit() else None


def _ssl_context():
    """建立 SSL context。預設正常驗證;WEATHER_VERIFY_SSL=0 時關閉驗證(僅供本機憑證鏈異常時用)。"""
    ctx = ssl.create_default_context()
    if os.getenv("WEATHER_VERIFY_SSL", "1") == "0":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_from_cwa():
    """實際呼叫 CWA API 並解析「最近一個時段」的天氣。任何失敗都會丟例外,由外層接住。"""
    api_key = os.getenv("CWA_API_KEY", "")
    location_name = os.getenv("WEATHER_LOCATION", "桃園市")  # 設計上保留擴充,改城市只改環境變數

    params = urllib.parse.urlencode({
        "Authorization": api_key,
        "locationName": location_name,
    })
    url = f"{BASE_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ChargeAlertTW/1.0"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=_ssl_context()) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    # 已用 locationName 過濾,正常只會回一筆;仍做防呆
    locations = raw.get("records", {}).get("location", [])
    if not locations:
        raise ValueError(f"CWA 回傳查無地點:{location_name}")
    location = locations[0]

    # 把 weatherElement 轉成 {elementName: time[]} 方便取用
    elements = {e["elementName"]: e["time"] for e in location["weatherElement"]}

    def first_val(name):
        try:
            return elements[name][0]["parameter"]["parameterName"]
        except (KeyError, IndexError):
            return None

    wx = first_val("Wx")       # 天氣現象,如「多雲時陰」
    pop = first_val("PoP")     # 降雨機率(%)
    min_t = first_val("MinT")  # 最低溫(°C)
    max_t = first_val("MaxT")  # 最高溫(°C)

    # 預報時段起訖(給前端日後顯示「預報區間」用)
    try:
        period_start = elements["Wx"][0]["startTime"]
        period_end = elements["Wx"][0]["endTime"]
    except (KeyError, IndexError):
        period_start = period_end = None

    return {
        "location": location["locationName"],
        "weather": wx,
        "pop": _to_int(pop),
        "min_temp": _to_int(min_t),
        "max_temp": _to_int(max_t),
        "advisory": _build_advisory(pop, wx),
        "period_start": period_start,
        "period_end": period_end,
        "source": "CWA F-C0032-001",
    }


def get_weather(force_refresh: bool = False):
    """
    對外主函式。回傳天氣 dict;WEATHER_CACHE_TTL 秒內重複呼叫直接吃快取。
    任何錯誤都回 ok=False 的 fallback,不會把例外往外丟。

    回傳範例:
      {"ok": True, "cached": False, "location": "桃園市", "weather": "晴時多雲",
       "pop": 0, "min_temp": 24, "max_temp": 29, "advisory": "...", ...}
    """
    location_name = os.getenv("WEATHER_LOCATION", "桃園市")
    cache_ttl = int(os.getenv("WEATHER_CACHE_TTL", "1800"))  # 預設 30 分鐘

    now = time.time()
    with _lock:
        cached = _cache["data"]
        fresh = cached is not None and (now - _cache["ts"]) < cache_ttl
        if fresh and not force_refresh:
            return {**cached, "ok": True, "cached": True}

    if not os.getenv("CWA_API_KEY", ""):
        return {
            "ok": False,
            "error": "CWA_API_KEY 未設定",
            "location": location_name,
            "advisory": "天氣服務尚未設定,請稍後再試。",
        }

    try:
        data = _fetch_from_cwa()
        with _lock:
            _cache["data"] = data
            _cache["ts"] = time.time()
        return {**data, "ok": True, "cached": False}
    except Exception as e:  # 網路 / 解析 / API 任何問題都走這
        # 有舊快取就回舊資料(標記 stale),沒有才回失敗 → graceful degradation
        with _lock:
            stale = _cache["data"]
        if stale is not None:
            return {**stale, "ok": True, "cached": True, "stale": True}
        return {
            "ok": False,
            "error": str(e),
            "location": location_name,
            "advisory": "天氣資料暫時無法取得,請稍後再試。",
        }


# 方便不經 Docker / FastAPI 就單獨測試:
#   設好環境變數後執行  python weather.py
# 本機若 SSL 憑證鏈報錯,加 WEATHER_VERIFY_SSL=0
if __name__ == "__main__":
    print(json.dumps(get_weather(force_refresh=True), ensure_ascii=False, indent=2))
