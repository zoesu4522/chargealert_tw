"""
postback_handler.py — 處理 LINE Rich Menu / 卡片按鈕的 postback 事件。

action 分派:
  home          🏠 我的縣市     → 預設桃園充電卡(之後接使用者偏好)
  menu_charging 🗺️ 選縣市充電   → 7 大都會 carousel(action=query)
  menu_weather  ☂️ 各地天氣     → 7 大都會 carousel(action=weather)
  overall       📊 整體統計     → 跨縣市總覽文字
  favorites     ⭐ 我的最愛     → (功能開發中,留接口)
  about         ℹ️ 關於         → 專案介紹
  query&city=X  查某縣市充電    → On-Demand 抓 + 充電卡
  weather&city=X 查某縣市天氣   → get_weather + 天氣卡

回傳統一格式:{"type": "text"|"flex", ...},由 main.py 的 reply 函式發送。
"""

from urllib.parse import parse_qs

import db
import fetcher
from weather import get_weather, city_to_cwa, CITY_NAME_MAP
import flex_builders as fb


def _city_zh(code):
    """英文 code → 中文顯示名(給卡片標題用)。"""
    return CITY_NAME_MAP.get(code, code)


def parse_postback(data: str) -> dict:
    """把 'action=query&city=Taipei' 解析成 {'action':'query','city':'Taipei'}。"""
    return {k: v[0] for k, v in parse_qs(data).items()}


def handle_postback(data: str) -> dict:
    """主分派。回傳 {"type": "text", "text": ...} 或 {"type": "flex", "altText":..., "contents":...}。"""
    params = parse_postback(data)
    action = params.get("action", "")
    city = params.get("city")

    if action == "home":
        return _charging_card("Taoyuan")

    if action == "menu_charging":
        return {
            "type": "flex",
            "altText": "選擇縣市看充電",
            "contents": fb.build_city_menu_carousel("query"),
        }

    if action == "menu_weather":
        return {
            "type": "flex",
            "altText": "選擇縣市看天氣",
            "contents": fb.build_city_menu_carousel("weather"),
        }

    if action == "query" and city:
        return _charging_card(city)

    if action == "weather" and city:
        return _weather_card(city)

    if action == "overall":
        return _overall_text()

    if action == "favorites":
        return {"type": "text", "text": "⭐ 我的最愛功能開發中,敬請期待!\n目前可以用「🗺️ 選縣市」查各地充電狀況。"}

    if action == "about":
        return {"type": "text", "text": (
            "🔌 ChargeAlert TW 充電站智慧通報\n\n"
            "・即時查詢全台充電站可用狀況\n"
            "・各縣市天氣 + 充電建議\n"
            "・桃園自動推播空位通知\n\n"
            "資料來源:TDX 運輸資料流通服務、中央氣象署 CWA"
        )}

    # 未知 action:友善 fallback
    return {"type": "text", "text": "請使用下方選單操作 🔌"}


def _charging_card(city):
    """查某縣市充電:桃園(主動縣市)直接讀 DB;其他走 On-Demand 抓。"""
    try:
        if city == "Taoyuan":
            stats = db.get_city_stats(city)
        else:
            stats = fetcher.fetch_city_on_demand(city)
        # On-Demand 失敗會回 {"error":..., "message":...}
        if stats.get("error"):
            return {"type": "text", "text": stats.get("message", "查詢失敗,請稍後再試")}
        return {
            "type": "flex",
            "altText": f"{_city_zh(city)} 充電概況",
            "contents": fb.build_city_charging_bubble(_city_zh(city), stats),
        }
    except Exception as e:
        return {"type": "text", "text": f"查詢 {_city_zh(city)} 時發生問題,請稍後再試 🙏"}


def _weather_card(city):
    try:
        weather = get_weather(city)
        return {
            "type": "flex",
            "altText": f"{_city_zh(city)} 天氣",
            "contents": fb.build_weather_bubble(_city_zh(city), weather),
        }
    except Exception:
        return {"type": "text", "text": f"查詢 {_city_zh(city)} 天氣時發生問題,請稍後再試 🙏"}


def _overall_text():
    try:
        s = db.get_overall_stats()
        return {"type": "text", "text": (
            f"📊 整體充電概況\n\n"
            f"監測站數:{s['station_count']} 站\n"
            f"充電槍總數:{s['total']} 支\n"
            f"目前可用:{s['available']} 支\n"
            f"・DC 快充 {s['dc_available']} / {s['dc_total']}\n"
            f"・AC 慢充 {s['ac_available']} / {s['ac_total']}"
        )}
    except Exception:
        return {"type": "text", "text": "查詢整體統計時發生問題,請稍後再試 🙏"}
