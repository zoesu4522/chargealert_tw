"""
ChargeAlert TW — 建立 LINE Rich Menu(6 格 Postback)
一次完成:建立選單物件 → 上傳圖片 → 設為所有人預設。

需求:
  - 環境變數 LINE_CHANNEL_ACCESS_TOKEN(從 .env 讀)
  - 同目錄有 rich_menu.png(2500x1686)

用法(EC2,在 webhook 容器或本機 python 皆可,只要有 requests + token):
  python setup_rich_menu.py            # 建立並套用
  python setup_rich_menu.py --list     # 列出現有 rich menu
  python setup_rich_menu.py --clean    # 刪除所有現有 rich menu(重做時用)
"""
import os
import sys
import json

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
IMG_PATH = "rich_menu.png"
BASE = "https://api.line.me/v2/bot"
DATA_BASE = "https://api-data.line.me/v2/bot"

# 6 格座標(來自 make_rich_menu.py 的輸出)+ 對應 postback action
AREAS = [
    {"label": "我的縣市", "x": 40,   "y": 40,  "w": 787, "h": 788, "action": "action=home"},
    {"label": "選縣市",   "x": 857,  "y": 40,  "w": 786, "h": 788, "action": "action=menu_charging"},
    {"label": "各地天氣", "x": 1673, "y": 40,  "w": 787, "h": 788, "action": "action=menu_weather"},
    {"label": "整體統計", "x": 40,   "y": 858, "w": 787, "h": 788, "action": "action=overall"},
    {"label": "我的訂閱", "x": 857,  "y": 858, "w": 786, "h": 788, "action": "action=my_subs"},
    {"label": "關於",     "x": 1673, "y": 858, "w": 787, "h": 788, "action": "action=about"},
]


def _headers(json_ct=True):
    h = {"Authorization": f"Bearer {TOKEN}"}
    if json_ct:
        h["Content-Type"] = "application/json"
    return h


def list_menus():
    r = requests.get(f"{BASE}/richmenu/list", headers=_headers())
    r.raise_for_status()
    menus = r.json().get("richmenus", [])
    print(f"現有 {len(menus)} 個 rich menu:")
    for m in menus:
        print(f"  {m['richMenuId']}  name={m.get('name')}")
    return menus


def clean_menus():
    for m in list_menus():
        rid = m["richMenuId"]
        r = requests.delete(f"{BASE}/richmenu/{rid}", headers=_headers())
        print(f"  刪除 {rid}: {r.status_code}")


def create_menu():
    if not TOKEN:
        print("❌ 找不到 LINE_CHANNEL_ACCESS_TOKEN,檢查 .env")
        sys.exit(1)
    if not os.path.exists(IMG_PATH):
        print(f"❌ 找不到 {IMG_PATH}")
        sys.exit(1)

    # 1) 建立 rich menu 物件
    body = {
        "size": {"width": 2500, "height": 1686},
        "selected": True,
        "name": "ChargeAlert TW 主選單",
        "chatBarText": "開啟選單",
        "areas": [
            {
                "bounds": {"x": a["x"], "y": a["y"], "width": a["w"], "height": a["h"]},
                "action": {"type": "postback", "data": a["action"], "displayText": a["label"]},
            }
            for a in AREAS
        ],
    }
    r = requests.post(f"{BASE}/richmenu", headers=_headers(), data=json.dumps(body))
    if r.status_code != 200:
        print(f"❌ 建立失敗 {r.status_code}: {r.text}")
        sys.exit(1)
    rich_menu_id = r.json()["richMenuId"]
    print(f"✅ 已建立 rich menu: {rich_menu_id}")

    # 2) 上傳圖片
    with open(IMG_PATH, "rb") as f:
        r = requests.post(
            f"{DATA_BASE}/richmenu/{rich_menu_id}/content",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "image/png"},
            data=f.read(),
        )
    if r.status_code != 200:
        print(f"❌ 上傳圖片失敗 {r.status_code}: {r.text}")
        sys.exit(1)
    print("✅ 圖片已上傳")

    # 3) 設為所有人預設
    r = requests.post(f"{BASE}/user/all/richmenu/{rich_menu_id}", headers=_headers())
    if r.status_code != 200:
        print(f"❌ 設為預設失敗 {r.status_code}: {r.text}")
        sys.exit(1)
    print("✅ 已設為所有使用者的預設選單")
    print(f"\n完成!Rich Menu ID: {rich_menu_id}")
    print("到手機上重開 LINE Bot 聊天室,下方應出現選單。")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--list":
        list_menus()
    elif arg == "--clean":
        clean_menus()
    else:
        create_menu()
