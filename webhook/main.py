"""
ChargeAlert TW — LINE Webhook (Phase 6 / Step 1:ngrok echo 測試版)

這一版只做最小的事,目的是先打通 LINE <-> 你的程式 這條路:
- 接收 LINE webhook 事件
- 用 channel secret 驗證 X-Line-Signature(HMAC-SHA256)
- 先秒回 200(LINE 有逾時限制),再到背景把訊息原樣回覆(echo)
- 這個階段「不碰資料庫」。等管線通了,下一步再接 LLM + MySQL。
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

load_dotenv()  # 讀取專案根目錄的 .env

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chargealert.webhook")

app = FastAPI(title="ChargeAlert TW Webhook")


def verify_signature(body: bytes, signature: str) -> bool:
    """
    用 channel secret 對「原始 request body」算 HMAC-SHA256,再 base64,
    比對 LINE 放在 X-Line-Signature 的簽章。
    重點:一定要用「原始 bytes」,不能用 parse 過再 dump 出來的 JSON,
    不然空白/順序不同會導致簽章對不上。
    """
    if not LINE_CHANNEL_SECRET:
        logger.warning("LINE_CHANNEL_SECRET 沒設定,無法驗簽")
        return False
    mac = hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature or "")


async def reply_to_line(reply_token: str, text: str) -> None:
    """
    呼叫 LINE Reply API 回覆使用者。
    用 reply token 回覆是免費的,也不會吃掉你的主動推播(push)額度。
    """
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


async def handle_events(events: list) -> None:
    """
    背景處理事件。Step 1 只做 echo:使用者傳什麼文字,就回一樣的文字。
    （之後這裡會換成:解析意圖 -> 查 MySQL -> LLM 組白話回覆。）
    """
    for event in events:
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "text":
            continue
        reply_token = event.get("replyToken")
        user_text = message.get("text", "")
        if reply_token:
            await reply_to_line(reply_token, f"你說:{user_text}")


@app.get("/")
async def health():
    """健康檢查。瀏覽器打開首頁應該看到這個 JSON,代表服務有起來。"""
    return {"status": "ok", "service": "chargealert-webhook"}


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(default=""),
):
    body = await request.body()

    if not verify_signature(body, x_line_signature):
        # 驗簽不過 = 不是 LINE 發的,或是 secret 設錯了,直接擋掉
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body or b"{}")
    events = payload.get("events", [])

    # 先把實際處理丟到背景,讓這支 request 立刻回 200。
    # （LINE 在你按 Verify 時會送一筆空的 events,這裡會直接回 200 通過。）
    background_tasks.add_task(handle_events, events)
    return {"status": "ok"}
