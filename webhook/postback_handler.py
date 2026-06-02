"""
postback_handler.py — 處理 LINE Rich Menu / 卡片按鈕的 postback 事件。

action 分派:
  home          🏠 我的縣市     → 預設桃園充電卡
  menu_charging 🗺️ 選縣市充電   → 7 大都會 carousel(action=query)
  menu_weather  ☂️ 各地天氣     → 7 大都會 carousel(action=weather)
  overall       📊 整體統計     → 跨縣市總覽文字
  my_subs       ⭐ 我的訂閱     → 列出使用者訂閱的站(可退訂)
  about         ℹ️ 關於         → 專案介紹
  query&city=X  查某縣市充電    → On-Demand 抓 + 充電卡
  weather&city=X 查某縣市天氣   → get_weather + 天氣卡
  subscribe&station=X   訂閱某站 → 寫入 user_subscriptions
  unsubscribe&station=X 退訂某站 → 軟刪除

需要 user_id 的 action(訂閱相關)由 main.py 從 event.source.userId 傳入。
"""

from urllib.parse import parse_qs

import db
import fetcher
from weather import get_weather, city_to_cwa, CITY_NAME_MAP
import flex_builders as fb


def _city_zh(code):
    return CITY_NAME_MAP.get(code, code)


def parse_postback(data: str) -> dict:
    return {k: v[0] for k, v in parse_qs(data).items()}


def handle_postback(data: str, user_id: str = None) -> dict:
    """主分派。user_id 來自 LINE event.source.userId(訂閱相關 action 需要)。"""
    params = parse_postback(data)
    action = params.get("action", "")
    city = params.get("city")
    station = params.get("station")

    if action == "home":
        return _charging_card("Taoyuan")

    if action == "menu_charging":
        return {"type": "flex", "altText": "選擇縣市看充電",
                "contents": fb.build_city_menu_carousel("query")}

    if action == "menu_weather":
        return {"type": "flex", "altText": "選擇縣市看天氣",
                "contents": fb.build_city_menu_carousel("weather")}

    if action == "query" and city:
        return _charging_card(city, user_id)

    if action == "weather" and city:
        return _weather_card(city)

    if action == "overall":
        return _overall_text()

    if action == "subscribe" and station:
        return _subscribe(user_id, station)

    if action == "unsubscribe" and station:
        return _unsubscribe(user_id, station)

    if action == "my_subs":
        return _my_subscriptions(user_id)

    if action == "pause":
        return _set_notify(user_id, False)

    if action == "resume":
        return _set_notify(user_id, True)

    if action == "set_window":
        return _set_window(user_id, params.get("s"), params.get("e"))

    if action == "districts" and city:
        return _list_districts(city)

    if action == "district" and city:
        d = params.get("d")
        return _stations_in_district(city, d)

    if action == "about":
        return {"type": "text", "text": (
            "🔌 ChargeAlert TW 充電站智慧通報\n\n"
            "・即時查詢全台充電站可用狀況\n"
            "・各縣市天氣 + 充電建議\n"
            "・訂閱充電站,有空位主動通知你\n\n"
            "資料來源:TDX 運輸資料流通服務、中央氣象署 CWA"
        )}

    return {"type": "text", "text": "請使用下方選單操作 🔌"}


def _charging_card(city, user_id=None):
    """查某縣市充電:回該縣市充電概況卡。"""
    try:
        if city == "Taoyuan":
            stats = db.get_city_stats(city)
        else:
            stats = fetcher.fetch_city_on_demand(city)
        if stats.get("error"):
            return {"type": "text", "text": stats.get("message", "查詢失敗,請稍後再試")}
        return {"type": "flex", "altText": f"{_city_zh(city)} 充電概況",
                "contents": fb.build_city_charging_bubble(_city_zh(city), stats, city_code=city)}
    except Exception:
        return {"type": "text", "text": f"查詢 {_city_zh(city)} 時發生問題,請稍後再試 🙏"}


def _weather_card(city):
    try:
        weather = get_weather(city)
        return {"type": "flex", "altText": f"{_city_zh(city)} 天氣",
                "contents": fb.build_weather_bubble(_city_zh(city), weather)}
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


def _subscribe(user_id, station_id):
    if not user_id:
        return {"type": "text", "text": "無法識別使用者,請稍後再試 🙏"}
    info = db.get_station_info(station_id)
    name = info.get("station_name", "充電站") if info else "充電站"
    # 先檢查是否已訂閱:已訂過就提示,不重複回「訂閱成功」
    if db.is_subscribed(user_id, station_id):
        return {"type": "text", "text": (
            f"✅ 你已經訂閱過了\n\n"
            f"📍 {name}\n\n"
            f"這站有空位時會通知你。\n"
            f"想取消可到「我的訂閱」管理。"
        )}
    ok = db.subscribe_station(user_id, station_id, name)
    if ok:
        # 訂閱當下若已有空位,順便告知現況(避免「訂了卻沒反應」的盲點)
        try:
            stats = db.get_station_stats(station_id)
            avail = stats.get("available", 0)
        except Exception:
            avail = 0
        if avail > 0:
            now_line = f"✅ 目前有 {avail} 個空位,可直接前往!\n\n"
        else:
            now_line = "目前暫無空位。\n\n"
        return {"type": "text", "text": (
            f"🔔 已訂閱成功!\n\n"
            f"📍 {name}\n\n"
            f"{now_line}"
            f"之後有空位時會主動通知你\n"
            f"(同站每小時最多通知一次)"
        )}
    return {"type": "text", "text": "訂閱失敗,請稍後再試 🙏"}


def _unsubscribe(user_id, station_id):
    if not user_id:
        return {"type": "text", "text": "無法識別使用者,請稍後再試 🙏"}
    info = db.get_station_info(station_id)
    name = info.get("station_name", "充電站") if info else "充電站"
    ok = db.unsubscribe_station(user_id, station_id)
    if ok:
        return {"type": "text", "text": (
            f"🔕 已取消訂閱\n\n"
            f"📍 {name}\n\n"
            f"不會再收到這站的通知。"
        )}
    return {"type": "text", "text": "取消訂閱失敗,請稍後再試 🙏"}


def _my_subscriptions(user_id):
    if not user_id:
        return {"type": "text", "text": "無法識別使用者,請稍後再試 🙏"}
    subs = db.get_user_subscriptions(user_id)
    enabled = db.get_notify_enabled(user_id)
    window = db.get_notify_window(user_id)
    if not subs:
        # 沒訂閱也讓使用者能看到/切換通知總開關
        state = "🔔 通知已開啟" if enabled else "🔕 通知已暫停"
        return {"type": "text", "text": (
            f"你目前沒有訂閱任何充電站。\n"
            f"查詢充電站後,點「🔔 訂閱這站」即可加入。\n\n"
            f"目前狀態:{state}"
        )}
    return {"type": "flex", "altText": "我的訂閱",
            "contents": fb.build_subscriptions_carousel(
                _enrich_subscriptions(subs), notify_enabled=enabled, window=window)}


def _enrich_subscriptions(subs):
    """為每個訂閱站補上地址 + 即時可用狀態,給訂閱卡顯示。"""
    enriched = []
    for s in subs:
        sid = s.get("station_id")
        item = dict(s)
        info = db.get_station_info(sid) if sid else None
        if info:
            item["address"] = info.get("address") or ""
            item["city"] = info.get("city") or ""
        try:
            st = db.get_station_stats(sid) if sid else None
            if st:
                item["available"] = st.get("available", 0)
                item["total"] = st.get("total", 0)
        except Exception:
            pass
        enriched.append(item)
    return enriched


def _set_notify(user_id, enabled):
    if not user_id:
        return {"type": "text", "text": "無法識別使用者,請稍後再試 🙏"}
    db.set_notify_enabled(user_id, enabled)
    # 設定後直接回「更新後的我的訂閱」,使用者馬上看到新狀態 + 可再切換,
    # 不用重新點「我的訂閱」。
    return _my_subscriptions(user_id)


def _set_window(user_id, s, e):
    if not user_id:
        return {"type": "text", "text": "無法識別使用者,請稍後再試 🙏"}
    try:
        start = int(s)
        end = int(e)
    except (TypeError, ValueError):
        return {"type": "text", "text": "時段設定有誤,請再試一次 🙏"}
    db.set_notify_window(user_id, start, end)
    # 設定後回更新的我的訂閱,馬上看到新時段
    return _my_subscriptions(user_id)


def _list_districts(city):
    """列出某縣市的行政區選單。資料未到位時給友善提示。"""
    try:
        districts = db.get_districts(city)
        if not districts:
            return {"type": "text", "text": (
                f"{_city_zh(city)} 的分區資料準備中 🚧\n"
                f"可以直接打地名或站名查詢(例如「中壢」)。"
            )}
        return {"type": "flex", "altText": f"{_city_zh(city)} 依區找站",
                "contents": fb.build_districts_carousel(city, _city_zh(city), districts)}
    except Exception:
        return {"type": "text", "text": "查詢分區時發生問題,請稍後再試 🙏"}


def _stations_in_district(city, district):
    """列出某縣市某區的充電站(可訂閱)。"""
    if not district:
        return {"type": "text", "text": "請選擇一個區 🙏"}
    try:
        stations = db.get_stations_by_district(city, district, limit=10)
        if not stations:
            return {"type": "text", "text": f"{district}目前查無充電站。"}
        with_stats = []
        for st in stations:
            stats = db.get_station_stats(st["station_id"])
            with_stats.append((st, stats))
        return {"type": "flex", "altText": f"{district} 充電站",
                "contents": fb.build_stations_carousel(with_stats)}
    except Exception:
        return {"type": "text", "text": "查詢該區充電站時發生問題,請稍後再試 🙏"}