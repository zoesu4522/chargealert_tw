"""
ChargeAlert TW — LINE Webhook (Phase 6 / Step 3:接上大腦)

流程:LINE 訊息 -> 驗簽 -> 解析意圖(Bedrock)-> 查 MySQL(真實數字)
       -> Bedrock 組白話回覆 -> 回 LINE

防幻覺原則:所有「數字」都來自 db.py 的查詢,LLM 只負責把數據講成人話。
"""

import os
import json
import hmac
import base64
import hashlib
import logging

import httpx
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from weather import get_weather

import db
import bedrock_client

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chargealert.webhook")

app = FastAPI(title="ChargeAlert TW Webhook")


def verify_signature(body: bytes, signature: str) -> bool:
    if not LINE_CHANNEL_SECRET:
        logger.warning("LINE_CHANNEL_SECRET 沒設定,無法驗簽")
        return False
    mac = hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature or "")


async def reply_to_line(reply_token: str, text: str) -> None:
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(LINE_REPLY_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("LINE 回覆失敗 %s: %s", resp.status_code, resp.text)


def _format_overall_facts(stats):
    """把整體統計組成給 LLM 的事實文字。"""
    return (
        f"目前監測的充電站總數:{stats['station_count']} 站\n"
        f"充電槍總數:{stats['total']} 支\n"
        f"目前空閒可用:{stats['available']} 支\n"
        f"  其中 AC 慢充可用 {stats['ac_available']} / 共 {stats['ac_total']} 支\n"
        f"  其中 DC 快充可用 {stats['dc_available']} / 共 {stats['dc_total']} 支"
    )


def _format_station_facts(name, stats):
    """把單站統計組成給 LLM 的事實文字。"""
    return (
        f"充電站:{name}\n"
        f"充電槍總數:{stats['total']} 支\n"
        f"目前空閒可用:{stats['available']} 支\n"
        f"  AC 慢充可用 {stats['ac_available']} / 共 {stats['ac_total']} 支\n"
        f"  DC 快充可用 {stats['dc_available']} / 共 {stats['dc_total']} 支"
    )


def build_answer(user_text: str) -> str:
    """
    同步函式:解析意圖 -> 查 DB -> 組回覆。
    在背景工作裡呼叫(裡面有 boto3 / pymysql 的同步 IO)。
    """
    parsed = bedrock_client.parse_intent(user_text)
    intent = parsed["intent"]
    keyword = parsed["keyword"]
    logger.info("意圖=%s keyword=%r", intent, keyword)

    if intent == "overall":
        stats = db.get_overall_stats()
        facts = _format_overall_facts(stats)
        return bedrock_client.compose_reply(user_text, facts)

    if intent == "station":
        if not keyword:
            return "請告訴我你想查哪個地點或站名,例如「中壢有位子嗎」🔌"
        matches = db.search_stations_by_name(keyword)
        if not matches:
            return f"目前查不到含「{keyword}」的充電站,換個地名或店名試試看?"
        if len(matches) > 1:
            # 命中多站:列出來讓使用者挑,避免回錯站
            names = "\n".join(f"・{m['station_name']}" for m in matches)
            return f"找到幾個符合「{keyword}」的站,你是指哪一個呢?\n{names}"
        # 剛好一站:查它的即時狀態
        station = matches[0]
        stats = db.get_station_stats(station["station_id"])
        facts = _format_station_facts(station["station_name"], stats)
        return bedrock_client.compose_reply(user_text, facts)

    # other:給個友善的引導
    return (
        "嗨!我是 ChargeAlert TW 充電站小幫手 🔌\n"
        "你可以問我「現在總共有多少充電槍可用」,"
        "或某個地點「中壢有位子嗎」,我幫你查即時狀態!"
    )


async def handle_events(events: list) -> None:
    for event in events:
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "text":
            continue
        reply_token = event.get("replyToken")
        user_text = message.get("text", "")
        if not reply_token:
            continue
        try:
            answer = build_answer(user_text)
        except Exception as e:
            logger.exception("處理訊息失敗: %s", e)
            answer = "抱歉,系統忙碌中,請稍後再試一次 🙏"
        await reply_to_line(reply_token, answer)


@app.get("/")
async def health():
    return {"status": "ok", "service": "chargealert-webhook"}


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(default=""),
):
    body = await request.body()
    if not verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body or b"{}")
    events = payload.get("events", [])
    background_tasks.add_task(handle_events, events)
    return {"status": "ok"}


#後台儀表板 API
#前端靜態頁面(/dashboard)會 fetch 這些端點拿資料。
#之後天氣 API 也加在這裡(例如 /api/weather),前端打同一個後端。

@app.get("/api/weather")
def api_weather():
    return get_weather()

@app.get("/api/stats")
async def api_stats():
    """整體統計:給 KPI 數字卡 + AC/DC 長條圖用。"""
    return db.get_overall_stats()


@app.get("/api/status-distribution")
async def api_status_distribution():
    """狀態分布:給圓餅圖用(空閒/使用中/離線)。"""
    return {"distribution": db.get_status_distribution()}


@app.get("/api/top-stations")
async def api_top_stations():
    """可用數最多的站排名:給 Top 10 橫條圖用。"""
    
@app.get("/api/history")
async def api_history(hours: int = 24, type: str = "ALL"):
    """可用量曲線:最近 N 小時的時間序列。type=ALL/AC/DC"""
    ptype = (type or "ALL").upper()
    if ptype not in ("ALL", "AC", "DC"):
        ptype = "ALL"
    hours = max(1, min(hours, 24 * 14))   # 限制 1 小時 ~ 14 天,防亂查
    return {"history": db.get_history(hours=hours, power_type=ptype)}
