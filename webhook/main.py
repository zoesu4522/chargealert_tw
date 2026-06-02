"""
ChargeAlert TW — LINE Webhook

流程:LINE 訊息/postback -> 驗簽 -> 查 MySQL(真實數字)-> 回 LINE。
防幻覺原則:所有「數字」都來自 db.py 的查詢。

訂閱制:文字查站回帶「🔔 訂閱這站」按鈕的卡片;postback 處理訂閱/退訂/我的訂閱。
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
import postback_handler
import flex_builders as fb
import rate_limit

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


def _build_messages(reply):
    """把 handler 回傳的統一格式轉成 LINE messages 陣列。
    reply 可為 str / {"type":"text",...} / {"type":"flex",...}。"""
    if isinstance(reply, str):
        return [{"type": "text", "text": reply}]
    if reply.get("type") == "flex":
        return [{
            "type": "flex",
            "altText": reply.get("altText", "ChargeAlert TW"),
            "contents": reply["contents"],
        }]
    return [{"type": "text", "text": reply.get("text", "")}]


async def reply_to_line(reply_token: str, reply) -> None:
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"replyToken": reply_token, "messages": _build_messages(reply)}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(LINE_REPLY_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("LINE 回覆失敗 %s: %s", resp.status_code, resp.text)


def _format_overall_facts(stats):
    return (
        f"目前監測的充電站總數:{stats['station_count']} 站\n"
        f"充電槍總數:{stats['total']} 支\n"
        f"目前空閒可用:{stats['available']} 支\n"
        f"  其中 AC 慢充可用 {stats['ac_available']} / 共 {stats['ac_total']} 支\n"
        f"  其中 DC 快充可用 {stats['dc_available']} / 共 {stats['dc_total']} 支"
    )


def build_answer(user_text: str):
    """
    解析意圖 -> 查 DB -> 組回覆。
    - overall:走 LLM 講人話(需要自然語言彙整)
    - station:直接回帶訂閱按鈕的站卡(跳過 LLM,卡片更清楚也不耗 Bedrock 配額)
    回傳:str 或 flex dict。
    """
    parsed = bedrock_client.parse_intent(user_text)
    intent = parsed["intent"]
    keyword = parsed["keyword"]
    logger.info("意圖=%s keyword=%r", intent, keyword)

    if intent == "overall":
        stats = db.get_overall_stats()
        facts = _format_overall_facts(stats)
        # LLM 講人話;Bedrock 不可用(配額/憑證)時退回純文字統計
        try:
            return bedrock_client.compose_reply(user_text, facts)
        except Exception:
            logger.warning("compose_reply 失敗,改回純文字統計")
            return (
                f"📊 整體充電概況\n\n"
                f"監測站數:{stats['station_count']} 站\n"
                f"充電槍總數:{stats['total']} 支\n"
                f"目前可用:{stats['available']} 支\n"
                f"・DC 快充 {stats['dc_available']} / {stats['dc_total']}\n"
                f"・AC 慢充 {stats['ac_available']} / {stats['ac_total']}"
            )

    if intent == "station":
        if not keyword:
            return "請告訴我你想查哪個地點或站名,例如「中壢有位子嗎」🔌"
        matches = db.search_stations_by_name(keyword, limit=10)
        if not matches:
            return f"目前查不到含「{keyword}」的充電站,換個地名或店名試試看?"
        # 對每站查即時統計,組成帶訂閱鈕的卡片
        with_stats = []
        for m in matches:
            stats = db.get_station_stats(m["station_id"])
            with_stats.append((m, stats))
        if len(with_stats) == 1:
            info, stats = with_stats[0]
            return {"type": "flex", "altText": f"{info['station_name']}",
                    "contents": fb.build_station_detail_bubble(info, stats)}
        return {"type": "flex", "altText": f"找到 {len(with_stats)} 個符合的站",
                "contents": fb.build_stations_carousel(with_stats)}

    return (
        "嗨!我是 ChargeAlert TW 充電站小幫手 🔌\n"
        "💡 直接打地名或站名(例如「中壢」),就能查附近的站、即時空位,還能訂閱通知!\n"
        "或問我「現在總共有多少充電槍可用」。"
    )


async def handle_events(events: list, acquired_flags: list = None) -> None:
    if acquired_flags is None:
        acquired_flags = [None] * len(events)
    for event, acquired in zip(events, acquired_flags):
        etype = event.get("type")
        reply_token = event.get("replyToken")
        if not reply_token:
            continue
        user_id = event.get("source", {}).get("userId")

        # ── postback:Rich Menu / 卡片按鈕 ──
        if etype == "postback":
            data = event.get("postback", {}).get("data", "")
            # acquired 由 webhook 同步段先判定:
            #   False = 慢操作但沒搶到鎖(連點被擋) / True = 搶到(處理完要 release) / None = 非慢操作
            if acquired is False:
                await reply_to_line(reply_token, {"type": "text", "text": "⏳ 操作太快,請稍候一下再點 🙏"})
                continue
            try:
                reply = postback_handler.handle_postback(data, user_id)
            except Exception as e:
                logger.exception("處理 postback 失敗: %s", e)
                reply = "抱歉,系統忙碌中,請稍後再試一次 🙏"
            finally:
                if acquired:
                    rate_limit.release(user_id)
            await reply_to_line(reply_token, reply)
            continue

        # ── message:文字訊息 ──
        if etype == "message":
            message = event.get("message", {})
            if message.get("type") != "text":
                continue
            user_text = message.get("text", "")
            if acquired is False:
                await reply_to_line(reply_token, {"type": "text", "text": "⏳ 操作太快,請稍候一下再點 🙏"})
                continue
            try:
                answer = build_answer(user_text)
            except Exception as e:
                logger.exception("處理訊息失敗: %s", e)
                answer = "抱歉,系統忙碌中,請稍後再試一次 🙏"
            finally:
                if acquired:
                    rate_limit.release(user_id)
            await reply_to_line(reply_token, answer)
            continue


@app.get("/")
async def health():
    return {"status": "ok", "service": "chargealert-webhook"}


def _event_needs_cooldown(event):
    """
    判斷此 event 是否要套冷卻防連點。
    涵蓋「會跳出卡片、連點會洗版」的互動;排除 pause/resume(狀態切換,
    使用者可能暫停後馬上想恢復,不該被冷卻擋)。
    """
    etype = event.get("type")
    if etype == "message" and event.get("message", {}).get("type") == "text":
        return True
    if etype == "postback":
        data = event.get("postback", {}).get("data", "")
        # 狀態切換類不冷卻(暫停/恢復要能連續操作)
        if data in ("action=pause", "action=resume", "action=set_window") or data.startswith("action=set_window"):
            return False
        return True
    return False


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

    # 防連點:在這個「同步段」就套用冷卻鎖。
    # FastAPI 的同步程式碼在 event loop 裡循序執行,並行的多個 webhook 請求
    # 會在此一個一個通過 try_acquire,第一個放行、冷卻期(3秒)內的其餘被擋,
    # 從源頭分勝負。冷卻式不需 release,時間到自然過期。
    # acquired_flags[i]: True=放行(可處理) / False=冷卻內被擋 / None=不需冷卻。
    acquired_flags = []
    for ev in events:
        if _event_needs_cooldown(ev):
            uid = ev.get("source", {}).get("userId")
            acquired_flags.append(rate_limit.try_acquire(uid))
        else:
            acquired_flags.append(None)

    background_tasks.add_task(handle_events, events, acquired_flags)
    return {"status": "ok"}


#後台儀表板 API
@app.get("/api/weather")
def api_weather(city: str = "Taoyuan"):
    return get_weather(city)

@app.get("/api/stats")
async def api_stats(city: str = ""):
    # city 給定且非 "all" → 只算該縣市;否則算全部(累積涵蓋)
    if city and city.lower() != "all":
        return db.get_city_stats(city)
    return db.get_overall_stats()

@app.get("/api/status-distribution")
async def api_status_distribution(city: str = ""):
    if city and city.lower() != "all":
        return {"distribution": db.get_status_distribution_by_city(city)}
    return {"distribution": db.get_status_distribution()}

@app.get("/api/top-stations")
async def api_top_stations():
    return {"stations": db.get_top_available_stations(limit=10)}

@app.get("/api/history")
async def api_history(hours: int = 24, type: str = "ALL"):
    ptype = (type or "ALL").upper()
    if ptype not in ("ALL", "AC", "DC"):
        ptype = "ALL"
    hours = max(1, min(hours, 24 * 14))
    return {"history": db.get_history(hours=hours, power_type=ptype)}

@app.get("/api/activity")
async def api_activity(hours: int = 48):
    hours = max(1, min(hours, 24 * 14))
    return {"activity": db.get_activity(hours=hours)}