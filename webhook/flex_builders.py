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


def build_city_charging_bubble(city_zh, stats):
    """單一縣市充電統計卡。stats 來自 db.get_city_stats / fetcher。"""
    available = stats.get("available", 0)
    total = stats.get("total", 0)
    station_count = stats.get("station_count", 0)

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
            "type": "box", "layout": "vertical", "paddingAll": "lg",
            "contents": [{
                "type": "button", "style": "primary", "color": GREEN, "height": "sm",
                "action": {"type": "postback", "label": "☂️ 看這裡的天氣",
                           "data": f"action=weather&city={_city_code_from_zh(city_zh)}"},
            }],
        },
    }


def build_weather_bubble(city_zh, weather):
    """單一縣市天氣卡。weather 來自 get_weather()。"""
    if not weather.get("ok"):
        body_text = weather.get("advisory", "天氣資料暫時無法取得")
        temp_line = ""
        pop_line = ""
        emoji = "🌤️"
    else:
        emoji = _weather_emoji(weather.get("weather"))
        wx = weather.get("weather", "")
        mn = weather.get("min_temp")
        mx = weather.get("max_temp")
        pop = weather.get("pop")
        temp_line = f"{mn}–{mx}°C" if mn is not None and mx is not None else ""
        pop_line = f"降雨機率 {pop}%" if pop is not None else ""
        body_text = weather.get("advisory", "")

    body_contents = [
        {"type": "text", "text": f"{emoji} {weather.get('weather', '')}",
         "size": "xl", "weight": "bold", "color": "#1A1A1A", "wrap": True},
    ]
    info_row = []
    if temp_line:
        info_row.append({"type": "text", "text": f"🌡️ {temp_line}", "size": "sm", "color": "#555555", "flex": 1})
    if pop_line:
        info_row.append({"type": "text", "text": f"💧 {pop_line}", "size": "sm", "color": "#555555", "flex": 1})
    if info_row:
        body_contents.append({"type": "box", "layout": "horizontal", "margin": "md", "contents": info_row})

    body_contents.append({"type": "separator", "margin": "md", "color": "#D0E8D0"})
    body_contents.append({"type": "text", "text": body_text, "size": "sm",
                          "color": "#666666", "wrap": True, "margin": "md"})

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#1976D2",
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
    """7 大都會選單(carousel)。action=query(充電) 或 weather(天氣)。"""
    header_text = "🗺️ 選擇縣市看充電" if action == "query" else "☂️ 選擇縣市看天氣"
    head_color = GREEN if action == "query" else "#1976D2"
    bubbles = []
    for code, zh, emoji in MAJOR_CITIES:
        bubbles.append({
            "type": "bubble",
            "size": "micro",
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "md", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": emoji, "size": "xxl", "align": "center"},
                    {"type": "text", "text": zh, "size": "sm", "weight": "bold",
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
