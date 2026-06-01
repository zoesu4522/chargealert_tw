import os
import ssl
import json
import time
import threading
import urllib.parse
import urllib.request
 
#固定設定
DATASET = "F-C0032-001"
BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/" + DATASET
HTTP_TIMEOUT = 8  # 對外請求逾時秒數
 
# 縣市英文 code → CWA 中文名(注意「臺」非「台」)。
# 與 config.CITY_NAME_MAP 對齊;webhook 無 config.py 故在此自包含。
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
 
DEFAULT_CITY = "Taoyuan"
 
 
def city_to_cwa(city):
    """
    把使用者傳來的縣市轉成 CWA 要的中文名。
    - 英文 code(Taipei) → 查表得「臺北市」
    - 已是中文(臺北市/台北市)→ 正規化「台」為「臺」後直接用
    查不到就回桃園市(安全預設)。
    """
    if not city:
        return CITY_NAME_MAP[DEFAULT_CITY]
    if city in CITY_NAME_MAP:
        return CITY_NAME_MAP[city]
    # 傳進來已是中文:把常見的「台」正規化成 CWA 的「臺」
    if city.endswith("市") or city.endswith("縣"):
        return city.replace("台", "臺")
    return CITY_NAME_MAP.get(city, CITY_NAME_MAP[DEFAULT_CITY])
 
 
#每個縣市各自一份快取:{ cwa_name: {"data":..., "ts":...} }
_cache = {}
_lock = threading.Lock()
 
 
#依降雨機率(%) 與天氣現象文字,產生給充電使用者的白話建議。純規則,不經 LLM。
def _build_advisory(pop, wx):
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
 
 
#把回傳的字串數字安全轉成 int,失敗回 None。
def _to_int(s):
    if s is None:
        return None
    s = str(s).strip()
    return int(s) if s.lstrip("-").isdigit() else None
 
 
#建立 SSL context。預設正常驗證;WEATHER_VERIFY_SSL=0 時關閉驗證(僅供本機憑證鏈異常時用)。
def _ssl_context():
    ctx = ssl.create_default_context()
    if os.getenv("WEATHER_VERIFY_SSL", "1") == "0":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx
 
 
#實際呼叫 CWA API 並解析「最近一個時段」的天氣。location_name 為 CWA 中文名。
#任何失敗都會丟例外,由外層接住。
def _fetch_from_cwa(location_name):
    api_key = os.getenv("CWA_API_KEY", "")
 
    params = urllib.parse.urlencode({
        "Authorization": api_key,
        "locationName": location_name,
    })
    url = f"{BASE_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ChargeAlertTW/1.0"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=_ssl_context()) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
 
    #已用 locationName 過濾,正常只會回一筆;仍做防呆
    locations = raw.get("records", {}).get("location", [])
    if not locations:
        raise ValueError(f"CWA 回傳查無地點:{location_name}")
    location = locations[0]
 
    #把 weatherElement 轉成 {elementName: time[]} 方便取用
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
 
    #預報時段起訖(給前端日後顯示「預報區間」用)
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
 
 
def get_weather(city: str = None, force_refresh: bool = False):
    """
    對外主函式。city 接英文 code(例 "Taipei")或中文名;不給則用桃園。
    回傳天氣 dict;同縣市 WEATHER_CACHE_TTL 秒內重複呼叫直接吃快取。
    任何錯誤都回 ok=False 的 fallback,不會把例外往外丟。
 
    回傳範例:
      {"ok": True, "cached": False, "location": "臺北市", "weather": "晴時多雲",
       "pop": 0, "min_temp": 24, "max_temp": 29, "advisory": "...", ...}
    """
    location_name = city_to_cwa(city)
    cache_ttl = int(os.getenv("WEATHER_CACHE_TTL", "1800"))  # 預設 30 分鐘
 
    now = time.time()
    with _lock:
        entry = _cache.get(location_name)
        fresh = entry is not None and (now - entry["ts"]) < cache_ttl
        if fresh and not force_refresh:
            return {**entry["data"], "ok": True, "cached": True}
 
    if not os.getenv("CWA_API_KEY", ""):
        return {
            "ok": False,
            "error": "CWA_API_KEY 未設定",
            "location": location_name,
            "advisory": "天氣服務尚未設定,請稍後再試。",
        }
 
    try:
        data = _fetch_from_cwa(location_name)
        with _lock:
            _cache[location_name] = {"data": data, "ts": time.time()}
        return {**data, "ok": True, "cached": False}
    except Exception as e:  #網路 / 解析 / API 任何問題都走這
        #有舊快取就回舊資料(標記 stale),沒有才回失敗 → graceful degradation
        with _lock:
            entry = _cache.get(location_name)
        if entry is not None:
            return {**entry["data"], "ok": True, "cached": True, "stale": True}
        return {
            "ok": False,
            "error": str(e),
            "location": location_name,
            "advisory": "天氣資料暫時無法取得,請稍後再試。",
        }
 
 
#方便不經 Docker / FastAPI 就單獨測試:
#  python weather.py            → 桃園
#  python weather.py Taipei     → 台北
#本機若 SSL 憑證鏈報錯,加 WEATHER_VERIFY_SSL=0
if __name__ == "__main__":
    import sys
    city_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(get_weather(city_arg, force_refresh=True), ensure_ascii=False, indent=2))