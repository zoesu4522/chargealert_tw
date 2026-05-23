import requests
import config


def send_line_message(text):
    """
    推播一則文字訊息給設定的 LINE 使用者
    text: 要發送的訊息內容
    回傳:成功 True / 失敗 False
    """
    if not config.LINE_CHANNEL_ACCESS_TOKEN or not config.LINE_USER_ID:
        print("  LINE 設定不完整,請檢查 .env 的 TOKEN 和 USER_ID")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": config.LINE_USER_ID,
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

def notify_available(changes):
    """把「變成空閒」的充電槍組成 Flex 卡片通知"""
    import db

    available = [c for c in changes if c["new_status"] == 1]
    if not available:
        print("📭 沒有新的空位,不發通知")
        return 0

    # 同站合併
    by_station = {}
    for c in available:
        by_station.setdefault(c["station_id"], []).append(c)

    # 為每個站組一張卡片(最多 10 張,LINE carousel 上限 12)
    bubbles = []
    for sid in list(by_station.keys())[:10]:
        count = len(by_station[sid])
        info = db.get_station_info(sid)
        if info and info.get("station_name"):
            bubbles.append(build_station_bubble(info, count))

    if not bubbles:
        # 都查不到基本資料,退回純文字
        print("⚠️  查無基本資料,改用純文字通知")
        text = f"⚡ 偵測到 {len(available)} 個充電站空位\n快去充電吧!🚗"
        send_line_message(text)
        return len(available)

    # 多張卡片用 carousel(可左右滑),單張就直接用 bubble
    if len(bubbles) == 1:
        flex_content = bubbles[0]
    else:
        flex_content = {
            "type": "carousel",
            "contents": bubbles,
        }

    alt_text = f"⚡ {len(bubbles)} 個充電站有空位"
    success = send_line_flex(alt_text, flex_content)
    return len(available) if success else 0

def send_line_flex(alt_text, flex_content):
    """
    推播 Flex Message(彈性訊息卡片)
    alt_text: 通知列預覽文字(LINE 通知列顯示這個)
    flex_content: Flex Message 的 JSON 結構
    """
    if not config.LINE_CHANNEL_ACCESS_TOKEN or not config.LINE_USER_ID:
        print("⚠️  LINE 設定不完整")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": config.LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": alt_text,
                "contents": flex_content,
            }
        ],
    }

    try:
        print("📤 正在發送 LINE Flex 卡片...")
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print("✅ Flex 卡片發送成功!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Flex 發送失敗:{e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   回應:{e.response.text[:300]}")
        return False

def build_station_bubble(info, count):
    """組裝一張充電站卡片(重新排版,清爽有層次)"""
    import db
    import re

    name = info.get("station_name", "充電站")
    address = info.get("address", "")
    station_id = info.get("station_id")

    from urllib.parse import quote
    map_url = f"https://maps.google.com/?q={quote(name)}"

    stats = db.get_station_stats(station_id)

    # 費率智慧精簡:從一長串費率裡抓出「X元/度」「X元/分」等關鍵價格
    def simplify_rate(rate_text):
        if not rate_text:
            return ""
        # 抓「數字+元+每度/度/分/小時」的片段
        matches = re.findall(r"\d+(?:\.\d+)?\s*元\s*(?:每度|/度|每分|/分|每小時|/小時)", rate_text)
        if matches:
            # 去重、最多取 2 個
            seen = []
            for m in matches:
                m = m.replace(" ", "")
                if m not in seen:
                    seen.append(m)
            return " / ".join(seen[:2])
        return ""

    rate = simplify_rate(info.get("charging_rate", ""))

    # ===== 頂部綠色橫幅 =====
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

    # ===== 主體 =====
    body_contents = [
        # 站名
        {
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "lg",
            "wrap": True,
            "color": "#1A1A1A",
        },
    ]

    # 地址
    if address:
        body_contents.append({
            "type": "text",
            "text": address,
            "size": "xs",
            "color": "#999999",
            "wrap": True,
            "margin": "sm",
        })

    # ===== 統計區(用淡綠底框包起來)=====
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
    # 分隔 + 總計
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

    # ===== 費率(精簡後,有才顯示)=====
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