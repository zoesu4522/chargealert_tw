"""
flex_builders.py — 各種 LINE Flex Message 卡片建構。
集中放這裡,讓 postback handler 專心處理流程。
配色沿用專案綠色系:#2E7D32(深綠) / #F1F8F1(淡綠底)。
"""

# 7 大都會(選單顯示用):(英文 code, 中文顯示名, emoji)
MAJOR_CITIES = [
    ("Taipei", "台北市", "🏙️"),
    ("NewTaipei", "新北市", "🌆"),
    ("Taoyuan", "桃園市", "✈️"),
    ("HsinchuCity", "新竹市", "🔬"),
    ("Taichung", "台中市", "🌃"),
    ("Tainan", "台南市", "🏛️"),
    ("Kaohsiung", "高雄市", "⚓"),
]

GREEN = "#2E7D32"
GREEN_LIGHT = "#F1F8F1"

# LINE Flex hero 圖(電動車充電示意圖,需公開 HTTPS URL,由 Caddy /img/ 提供)
HERO_IMAGE_URL = "https://chargealert.zoesu.dev/img/ev_hero.jpg"
IMG_BASE = "https://chargealert.zoesu.dev/img"

# 有專屬地標圖的縣市(其餘 fallback 用 ev_hero 通用圖)
CITY_HERO_CODES = {"Taipei", "NewTaipei", "Taoyuan", "HsinchuCity",
                   "Taichung", "Tainan", "Kaohsiung"}

def _hero(city_code=None):
    """
    共用的 hero 圖區塊。20:13 比例。
    給 city_code 且該縣市有專屬地標圖 → 用縣市圖;否則用通用 EV 圖。
    """
    if city_code and city_code in CITY_HERO_CODES:
        url = f"{IMG_BASE}/city_{city_code}.jpg"
    else:
        url = HERO_IMAGE_URL
    return {
        "type": "image",
        "url": url,
        "size": "full",
        "aspectRatio": "20:13",
        "aspectMode": "cover",
    }


# 依天氣現象文字挑 emoji(純規則)
def _weather_emoji(wx):
    if not wx:
        return "🌤️"
    if "雷" in wx:
        return "⛈️"
    if "雨" in wx:
        return "🌧️"
    if "陰" in wx:
        return "☁️"
    if "多雲" in wx:
        return "⛅"
    if "晴" in wx:
        return "☀️"
    return "🌤️"


def build_city_charging_bubble(city_zh, stats, city_code=None):
    """單一縣市充電統計卡。stats 來自 db.get_city_stats / fetcher。
    city_code:英文 code,用於「依區找站」按鈕(不給則從中文反查)。"""
    available = stats.get("available", 0)
    total = stats.get("total", 0)
    station_count = stats.get("station_count", 0)
    if city_code is None:
        city_code = _city_code_from_zh(city_zh)

    def stat_row(icon, label, avail, tot, is_total=False):
        color = GREEN if avail > 0 else "#BBBBBB"
        label_color = "#333333" if is_total else "#666666"
        weight = "bold" if is_total else "regular"
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": f"{icon} {label}", "size": "sm",
                 "color": label_color, "weight": weight, "flex": 5},
                {"type": "text", "text": f"{avail} / {tot}", "size": "sm",
                 "weight": "bold", "color": color, "align": "end", "flex": 3},
            ],
        }

    rows = []
    if stats.get("dc_total", 0) > 0:
        rows.append(stat_row("⚡", "DC 快充", stats.get("dc_available", 0), stats.get("dc_total", 0)))
    if stats.get("ac_total", 0) > 0:
        rows.append(stat_row("🔌", "AC 慢充", stats.get("ac_available", 0), stats.get("ac_total", 0)))
    rows.append({"type": "separator", "margin": "md", "color": "#D0E8D0"})
    rows.append(stat_row("✅", "可用總數", available, total, is_total=True))

    return {
        "type": "bubble",
        "size": "kilo",
        "hero": _hero(city_code),
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": GREEN,
            "paddingAll": "lg",
            "contents": [
                {"type": "text", "text": f"🔌 {city_zh} 充電概況", "color": "#FFFFFF",
                 "weight": "bold", "size": "lg"},
                {"type": "text", "text": f"監測 {station_count} 站", "color": "#D7EAD7",
                 "size": "xs", "margin": "sm"},
            ],
        },
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "lg", "spacing": "sm",
            "contents": [{
                "type": "box", "layout": "vertical", "backgroundColor": GREEN_LIGHT,
                "cornerRadius": "md", "paddingAll": "md", "spacing": "sm", "contents": rows,
            }],
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "lg", "spacing": "sm",
            "contents": [
                {
                    "type": "button", "style": "primary", "color": GREEN, "height": "sm",
                    "action": {"type": "postback", "label": "🔍 依區找站",
                               "data": f"action=districts&city={city_code}"},
                },
                {
                    "type": "button", "style": "secondary", "height": "sm",
                    "action": {"type": "postback", "label": "☂️ 看這裡的天氣",
                               "data": f"action=weather&city={city_code}"},
                },
            ],
        },
    }


def build_weather_bubble(city_zh, weather):
    """單一縣市天氣卡。weather 來自 get_weather()。大 emoji + 大溫度 + 降雨色塊。"""
    BLUE = "#1976D2"
    BLUE_LIGHT = "#E8F1FB"

    if not weather.get("ok"):
        # 資料拿不到的退化版
        return {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical", "backgroundColor": BLUE,
                "paddingAll": "lg",
                "contents": [{"type": "text", "text": f"☂️ {city_zh} 天氣",
                              "color": "#FFFFFF", "weight": "bold", "size": "lg"}],
            },
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "lg",
                "contents": [{"type": "text",
                              "text": weather.get("advisory", "天氣資料暫時無法取得,稍後會自動恢復。"),
                              "size": "sm", "color": "#666666", "wrap": True}],
            },
        }

    emoji = _weather_emoji(weather.get("weather"))
    wx = weather.get("weather", "")
    mn = weather.get("min_temp")
    mx = weather.get("max_temp")
    pop = weather.get("pop")
    advisory = weather.get("advisory", "")
    temp_text = f"{mn}–{mx}°" if mn is not None and mx is not None else "—"

    body_contents = [
        # 大 emoji 當主視覺
        {"type": "text", "text": emoji, "size": "5xl", "align": "center"},
        # 天氣文字
        {"type": "text", "text": wx, "size": "lg", "weight": "bold",
         "color": "#1A1A1A", "align": "center", "wrap": True, "margin": "sm"},
        # 大溫度
        {"type": "text", "text": temp_text, "size": "xxl", "weight": "bold",
         "color": BLUE, "align": "center", "margin": "sm"},
    ]

    # 降雨機率色塊(淡藍底,突顯)
    if pop is not None:
        body_contents.append({
            "type": "box", "layout": "baseline", "margin": "lg",
            "backgroundColor": BLUE_LIGHT, "cornerRadius": "10px",
            "paddingAll": "md", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "💧 降雨機率", "size": "sm",
                 "color": "#555555", "flex": 0},
                {"type": "text", "text": f"{pop}%", "size": "lg", "weight": "bold",
                 "color": BLUE, "align": "end"},
            ],
        })

    # 充電建議(advisory)
    if advisory:
        body_contents.append({"type": "separator", "margin": "lg", "color": "#E0E0E0"})
        body_contents.append({"type": "text", "text": f"💡 {advisory}", "size": "xs",
                              "color": "#888888", "wrap": True, "margin": "lg"})

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": BLUE,
            "paddingAll": "lg",
            "contents": [
                {"type": "text", "text": f"☂️ {city_zh} 天氣", "color": "#FFFFFF",
                 "weight": "bold", "size": "lg"},
            ],
        },
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "lg", "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "lg",
            "contents": [{
                "type": "button", "style": "primary", "color": GREEN, "height": "sm",
                "action": {"type": "postback", "label": "🔌 看這裡的充電",
                           "data": f"action=query&city={_city_code_from_zh(city_zh)}"},
            }],
        },
    }


def build_city_menu_carousel(action):
    """7 大都會選單(carousel)。action=query(充電) 或 weather(天氣)。
    每張卡用該縣市的地標圖當 hero,取代原本的 emoji。"""
    head_color = GREEN if action == "query" else "#1976D2"
    bubbles = []
    for code, zh, emoji in MAJOR_CITIES:
        bubbles.append({
            "type": "bubble",
            "size": "kilo",
            "hero": _hero(code),  # 縣市地標圖(沒有的 fallback 通用圖)
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "md", "spacing": "xs",
                "contents": [
                    {"type": "text", "text": zh, "size": "md", "weight": "bold",
                     "align": "center", "color": "#1A1A1A", "wrap": True},
                ],
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "sm",
                "contents": [{
                    "type": "button", "style": "primary", "color": head_color, "height": "sm",
                    "action": {"type": "postback", "label": "查詢",
                               "data": f"action={action}&city={code}"},
                }],
            },
        })
    return {"type": "carousel", "contents": bubbles}


# 中文顯示名 → 英文 code(給卡片內按鈕回填 city 用)
_ZH_TO_CODE = {zh: code for code, zh, _ in MAJOR_CITIES}


def _city_code_from_zh(city_zh):
    # 卡片標題用的是顯示名(可能含「台」),正規化後查
    norm = city_zh.replace("臺", "台")
    return _ZH_TO_CODE.get(norm, "Taoyuan")


def build_station_detail_bubble(info, stats, subscribed=False):
    """
    單站詳情卡(含訂閱/退訂按鈕)。給文字查站的結果用。
    info: station_info 一筆(含 station_name, address, station_id)
    stats: get_station_stats 結果
    subscribed: True 顯示退訂鈕,False 顯示訂閱鈕
    """
    name = info.get("station_name") or "充電站"
    address = info.get("address") or ""
    sid = info.get("station_id")
    available = stats.get("available", 0)
    total = stats.get("total", 0)

    def stat_row(icon, label, avail, tot, is_total=False):
        color = GREEN if avail > 0 else "#BBBBBB"
        label_color = "#333333" if is_total else "#666666"
        weight = "bold" if is_total else "regular"
        return {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "text", "text": f"{icon} {label}", "size": "sm",
                 "color": label_color, "weight": weight, "flex": 5},
                {"type": "text", "text": f"{avail} / {tot}", "size": "sm",
                 "weight": "bold", "color": color, "align": "end", "flex": 3},
            ],
        }

    rows = []
    if stats.get("dc_total", 0) > 0:
        rows.append(stat_row("⚡", "DC 快充", stats.get("dc_available", 0), stats.get("dc_total", 0)))
    if stats.get("ac_total", 0) > 0:
        rows.append(stat_row("🔌", "AC 慢充", stats.get("ac_available", 0), stats.get("ac_total", 0)))
    rows.append({"type": "separator", "margin": "md", "color": "#D0E8D0"})
    rows.append(stat_row("✅", "可用總數", available, total, is_total=True))

    body_contents = [
        {"type": "text", "text": name, "weight": "bold", "size": "md",
         "wrap": True, "color": "#1A1A1A"},
    ]
    if address:
        body_contents.append({"type": "text", "text": address, "size": "xs",
                              "color": "#999999", "wrap": True, "margin": "sm"})
    body_contents.append({
        "type": "box", "layout": "vertical", "backgroundColor": GREEN_LIGHT,
        "cornerRadius": "md", "paddingAll": "md", "margin": "lg", "spacing": "sm",
        "contents": rows,
    })

    if subscribed:
        btn = {"type": "button", "style": "secondary", "height": "sm",
               "action": {"type": "postback", "label": "🔕 取消訂閱",
                          "data": f"action=unsubscribe&station={sid}"}}
    else:
        btn = {"type": "button", "style": "primary", "color": GREEN, "height": "sm",
               "action": {"type": "postback", "label": "🔔 訂閱這站",
                          "data": f"action=subscribe&station={sid}"}}

    return {
        "type": "bubble", "size": "kilo",
        "hero": _hero(),
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": GREEN,
            "paddingAll": "md",
            "contents": [{"type": "text", "text": "🔌 充電站", "color": "#FFFFFF",
                          "size": "xs", "weight": "bold"}],
        },
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "lg", "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "md", "contents": [btn]},
    }


def build_stations_carousel(stations_with_stats):
    """
    多站結果(carousel)。每張單站卡含訂閱鈕。
    stations_with_stats: [(info, stats), ...]
    """
    bubbles = [build_station_detail_bubble(info, stats)
               for info, stats in stations_with_stats[:10]]
    return {"type": "carousel", "contents": bubbles}


def build_subscriptions_carousel(subs, notify_enabled=True, window=(0, 24)):
    """
    我的訂閱清單(carousel)。
    第一張固定是「通知設定」卡(開/關切換 + 通知時段),
    後面每張是一個訂閱站 + 退訂按鈕。
    notify_enabled: 通知總開關;window: (start_hour, end_hour) 目前時段。
    """
    bubbles = []
    start, end = window

    # 時段顯示文字
    if start == 0 and end == 24:
        window_text = "⏰ 通知時段:全天"
    else:
        window_text = f"⏰ 通知時段:{start:02d}:00–{end:02d}:00"

    # ── 第一張:通知設定卡(開關 + 時段)──
    if notify_enabled:
        state_text = "🔔 通知開啟中"
        state_color = GREEN
        toggle_btn = {
            "type": "button", "style": "secondary", "height": "sm",
            "action": {"type": "postback", "label": "🔕 暫停所有通知",
                       "data": "action=pause"},
        }
    else:
        state_text = "🔕 通知已暫停"
        state_color = "#999999"
        toggle_btn = {
            "type": "button", "style": "primary", "color": GREEN, "height": "sm",
            "action": {"type": "postback", "label": "🔔 恢復通知",
                       "data": "action=resume"},
        }

    # 三個預設時段按鈕(整點、不跨夜)
    window_btns = [
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "postback", "label": "全天",
                    "data": "action=set_window&s=0&e=24"}},
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "postback", "label": "白天 08–22",
                    "data": "action=set_window&s=8&e=22"}},
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "postback", "label": "上班 09–18",
                    "data": "action=set_window&s=9&e=18"}},
    ]

    bubbles.append({
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": state_color,
            "paddingAll": "md",
            "contents": [{"type": "text", "text": "⚙️ 通知設定", "color": "#FFFFFF",
                          "size": "xs", "weight": "bold"}],
        },
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "lg", "spacing": "sm",
            "contents": [
                {"type": "text", "text": state_text, "weight": "bold", "size": "md",
                 "color": "#1A1A1A"},
                {"type": "separator", "margin": "md", "color": "#E0E0E0"},
                {"type": "text", "text": window_text, "size": "sm",
                 "color": "#555555", "margin": "md"},
                {"type": "text", "text": "選擇接收通知的時段:", "size": "xxs",
                 "color": "#999999", "margin": "sm"},
            ],
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "md", "spacing": "xs",
            "contents": [toggle_btn] + window_btns},
    })

    # ── 後面:每個訂閱站一張卡 ──
    for s in subs[:9]:  # 連同設定卡共 10 張(carousel 上限)
        name = s.get("station_name") or "充電站"
        sid = s.get("station_id")
        address = s.get("address") or ""
        avail = s.get("available")
        total = s.get("total")
        city_zh = s.get("city") or ""

        # hero:用站所在縣市的地標圖(查不到 city 就用通用 EV 圖)
        city_code = _city_code_from_zh(city_zh) if city_zh else None
        hero = _hero(city_code)

        body_items = [
            {"type": "text", "text": name, "weight": "bold", "size": "md",
             "wrap": True, "color": "#1A1A1A"},
        ]
        if address:
            body_items.append({"type": "text", "text": f"📍 {address}", "size": "xs",
                               "color": "#888888", "wrap": True, "margin": "sm"})

        # 即時可用:大字色塊(填滿 + 醒目)
        if total is not None and total > 0:
            ok = (avail or 0) > 0
            box_bg = GREEN_LIGHT if ok else "#F2F2F2"
            num_color = GREEN if ok else "#BBBBBB"
            label = "目前可用" if ok else "目前已滿"
            body_items.append({
                "type": "box", "layout": "vertical", "margin": "lg",
                "backgroundColor": box_bg, "cornerRadius": "10px", "paddingAll": "md",
                "spacing": "xs",
                "contents": [
                    {"type": "text", "text": label, "size": "xs", "color": "#888888"},
                    {"type": "box", "layout": "baseline", "contents": [
                        {"type": "text", "text": f"{avail or 0}", "size": "xxl",
                         "weight": "bold", "color": num_color, "flex": 0},
                        {"type": "text", "text": f"/ {total} 支", "size": "sm",
                         "color": "#999999", "margin": "sm", "flex": 0},
                    ]},
                ],
            })
            body_items.append({"type": "text", "text": "🔔 有空位時會通知你", "size": "xxs",
                               "color": "#AAAAAA", "margin": "md", "align": "center"})
        else:
            body_items.append({"type": "text", "text": "🔔 有空位時會通知你", "size": "xs",
                               "color": "#999999", "margin": "lg", "align": "center"})

        bubbles.append({
            "type": "bubble", "size": "kilo",
            "hero": hero,
            "header": {
                "type": "box", "layout": "vertical", "backgroundColor": GREEN,
                "paddingAll": "md",
                "contents": [{"type": "text", "text": "🔔 已訂閱", "color": "#FFFFFF",
                              "size": "xs", "weight": "bold"}],
            },
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "lg", "spacing": "sm",
                "contents": body_items,
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "md",
                "contents": [{
                    "type": "button", "style": "secondary", "height": "sm",
                    "action": {"type": "postback", "label": "🔕 取消訂閱",
                               "data": f"action=unsubscribe&station={sid}"},
                }],
            },
        })
    return {"type": "carousel", "contents": bubbles}


def build_districts_carousel(city_code, city_zh, districts):
    """
    某縣市的行政區選單(carousel)。每張卡一個區 + 站數 + 「看這區的站」按鈕。
    districts: [{"district":..., "cnt":...}, ...] 來自 db.get_districts
    """
    bubbles = []
    for d in districts[:12]:  # carousel 上限 12
        dname = d.get("district") or "未分區"
        cnt = d.get("cnt", 0)
        bubbles.append({
            "type": "bubble", "size": "micro",
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "md", "spacing": "xs",
                "contents": [
                    {"type": "text", "text": dname, "size": "md", "weight": "bold",
                     "align": "center", "color": "#1A1A1A", "wrap": True},
                    {"type": "text", "text": f"{cnt} 站", "size": "xs",
                     "align": "center", "color": "#999999"},
                ],
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "sm",
                "contents": [{
                    "type": "button", "style": "primary", "color": GREEN, "height": "sm",
                    "action": {"type": "postback", "label": "看這區",
                               "data": f"action=district&city={city_code}&d={dname}"},
                }],
            },
        })
    return {"type": "carousel", "contents": bubbles}