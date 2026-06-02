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
