import requests
import config

#推播一則文字訊息給指定 LINE 使用者。to 不給則用 config.LINE_USER_ID(向後相容)。
def send_line_message(text, to=None):
    target = to or config.LINE_USER_ID
    if not config.LINE_CHANNEL_ACCESS_TOKEN or not target:
        print("  LINE 設定不完整,請檢查 .env 的 TOKEN 和 USER_ID")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": target,
        "messages": [
            {"type": "text", "text": text}
        ],
    }

    try:
        print(" 正在發送 LINE 訊息...")
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(" LINE 訊息發送成功!")
        return True
    except requests.exceptions.RequestException as e:
        print(f" LINE 發送失敗:{e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   狀態碼:{e.response.status_code}")
            print(f"   回應:{e.response.text[:300]}")
        return False


#訂閱制推播:對每個「變成空閒」的站,查訂閱者(已含 1 小時冷卻),逐人 push 卡片。
#不再推給寫死的 LINE_USER_ID —— 沒人訂閱該站就不推。
def notify_available(changes):
    import db

    if not config.LINE_NOTIFY_ENABLED:
        available_count = sum(1 for c in changes if c["new_status"] == 1)
        if available_count > 0:
            print(f"📵 LINE 推播已停用(開發模式),本來要處理 {available_count} 個空位")
        return 0

    #只看「變成空閒(status=1)」的變化
    available = [c for c in changes if c["new_status"] == 1]
    if not available:
        print("📭 沒有新的空位,不發通知")
        return 0

    #同一站可能有多支槍同時變空,先依站去重(一站推一次卡片即可)
    station_ids = []
    for c in available:
        sid = c["station_id"]
        if sid not in station_ids:
            station_ids.append(sid)

    total_pushed = 0
    for sid in station_ids:
        #查這站「該收到推播」的訂閱者(active=1 且過了冷卻時間)
        subscribers = db.get_subscribers_to_notify(sid)
        if not subscribers:
            continue  #沒人訂這站(或都在冷卻中),跳過

        info = db.get_station_info(sid)
        if not info or not info.get("station_name"):
            continue
        bubble = build_station_bubble(info, 0)
        alt_text = f"⚡ {info['station_name']} 有空位"

        notified_ids = []
        for sub in subscribers:
            ok = send_line_flex(alt_text, bubble, to=sub["user_id"])
            if ok:
                notified_ids.append(sub["id"])
                total_pushed += 1

        #推成功的更新 last_notified_at(啟動 1 小時冷卻)
        if notified_ids:
            db.mark_notified(notified_ids)
            print(f"📱 {info['station_name']}:已推播給 {len(notified_ids)} 位訂閱者")

    if total_pushed == 0:
        print("📭 有空位變化,但沒有對應的訂閱者(或都在冷卻中)")
    return total_pushed


#推播 Flex Message 給指定使用者。to 不給則用 config.LINE_USER_ID。
def send_line_flex(alt_text, flex_content, to=None):
    target = to or config.LINE_USER_ID
    if not config.LINE_CHANNEL_ACCESS_TOKEN or not target:
        print("⚠️  LINE 設定不完整")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": target,
        "messages": [
            {
                "type": "flex",
                "altText": alt_text,
                "contents": flex_content,
            }
        ],
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f" Flex 發送失敗:{e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   回應:{e.response.text[:300]}")
        return False


def build_station_bubble(info, count):
    import db
    import re

    name = info.get("station_name", "充電站")
    address = info.get("address", "")
    station_id = info.get("station_id")

    from urllib.parse import quote
    map_url = f"https://maps.google.com/?q={quote(name)}"

    stats = db.get_station_stats(station_id)

    #費率智慧精簡:從一長串費率裡抓出「X元/度」「X元/分」等關鍵價格
    def simplify_rate(rate_text):
        if not rate_text:
            return ""
        matches = re.findall(r"\d+(?:\.\d+)?\s*元\s*(?:每度|/度|每分|/分|每小時|/小時)", rate_text)
        if matches:
            seen = []
            for m in matches:
                m = m.replace(" ", "")
                if m not in seen:
                    seen.append(m)
            return " / ".join(seen[:2])
        return ""

    rate = simplify_rate(info.get("charging_rate", ""))

    header = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#2E7D32",
        "paddingAll": "lg",
        "contents": [
            {
                "type": "text",
                "text": "⚡ 充電站有空位",
                "color": "#FFFFFF",
                "weight": "bold",
                "size": "lg",
            }
        ],
    }

    body_contents = [
        {
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "lg",
            "wrap": True,
            "color": "#1A1A1A",
        },
    ]

    if address:
        body_contents.append({
            "type": "text",
            "text": address,
            "size": "xs",
            "color": "#999999",
            "wrap": True,
            "margin": "sm",
        })

    def stat_row(icon, label, available, total, is_total=False):
        color = "#2E7D32" if available > 0 else "#BBBBBB"
        label_color = "#333333" if is_total else "#666666"
        label_weight = "bold" if is_total else "regular"
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": f"{icon} {label}", "size": "sm", "color": label_color, "weight": label_weight, "flex": 5},
                {"type": "text", "text": f"{available} / {total}", "size": "sm", "weight": "bold", "color": color, "align": "end", "flex": 2},
            ],
        }

    stat_rows = []
    if stats["dc_total"] > 0:
        stat_rows.append(stat_row("⚡", "DC 快充", stats["dc_available"], stats["dc_total"]))
    if stats["ac_total"] > 0:
        stat_rows.append(stat_row("🔌", "AC 慢充", stats["ac_available"], stats["ac_total"]))
    stat_rows.append({"type": "separator", "margin": "md", "color": "#D0E8D0"})
    stat_rows.append(stat_row("✅", "可用總數", stats["available"], stats["total"], is_total=True))

    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#F1F8F1",
        "cornerRadius": "md",
        "paddingAll": "md",
        "margin": "lg",
        "spacing": "sm",
        "contents": stat_rows,
    })

    if rate:
        body_contents.append({
            "type": "box",
            "layout": "baseline",
            "margin": "md",
            "contents": [
                {"type": "text", "text": "💰", "size": "sm", "flex": 0},
                {"type": "text", "text": rate, "size": "xs", "color": "#888888", "margin": "sm", "wrap": True},
            ],
        })

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": header,
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "lg",
            "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "lg",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#2E7D32",
                    "height": "sm",
                    "action": {"type": "uri", "label": "🗺️ 開啟導航", "uri": map_url},
                }
            ],
        },
    }
    return bubble