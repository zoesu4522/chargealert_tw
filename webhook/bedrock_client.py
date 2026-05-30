"""
Bedrock(Claude Haiku 4.5)模組,負責兩件事:

1. parse_intent():把使用者的話分類成意圖,並抽出站名關鍵字
2. compose_reply():把「資料庫查到的真實數字」交給 LLM 組成白話回覆

關鍵設計:LLM 只做「自然語言」的工作,所有事實數字都來自 MySQL 查詢,
不讓 LLM 自己編數量,避免幻覺。

用 EC2 的 IAM 角色(chargealert-ec2-bedrock)取得憑證,程式裡不需要任何金鑰。
"""

import json
import logging

import boto3

logger = logging.getLogger("chargealert.bedrock")

# 東京區 + Haiku 4.5 的跨區推論 profile(jp.* 開頭)
REGION = "ap-northeast-1"
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

# boto3 會自動透過 EC2 instance 的 IAM 角色拿臨時憑證,不用填 key
_client = boto3.client("bedrock-runtime", region_name=REGION)


def _invoke(system_prompt, user_text, max_tokens=400):
    """呼叫 Bedrock Converse API,回傳純文字。"""
    resp = _client.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


def parse_intent(user_text):
    """
    把使用者訊息分類成意圖。回傳 dict:
      {"intent": "overall" | "station" | "other", "keyword": "<站名關鍵字或空>"}

    - overall:問整體/全部/有沒有充電站可用之類的概況
    - station:問某個特定地點/站名(keyword 放抽出來的地名)
    - other:打招呼、無關問題等
    """
    system = (
        "你是一個意圖分類器,專門處理電動車充電站查詢。"
        "使用者會用中文問問題。請判斷意圖並只回傳 JSON,不要任何其他文字、不要 markdown。\n"
        "格式:{\"intent\": \"overall\" 或 \"station\" 或 \"other\", \"keyword\": \"地名或站名,沒有就空字串\"}\n"
        "規則:\n"
        "- 問整體、全部、總共、現在有多少可用、概況 -> overall\n"
        "- 問某個具體地點或店名(例如「中壢有位子嗎」「江園門市」)-> station,keyword 放那個地名\n"
        "- 打招呼、自我介紹、無關問題 -> other\n"
    )
    raw = _invoke(system, user_text, max_tokens=120)
    try:
        # 保險:去掉可能誤帶的 markdown code fence
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        intent = data.get("intent", "other")
        keyword = data.get("keyword", "") or ""
        if intent not in ("overall", "station", "other"):
            intent = "other"
        return {"intent": intent, "keyword": keyword.strip()}
    except Exception as e:
        logger.warning("意圖解析失敗,fallback 成 other: %s (raw=%r)", e, raw)
        return {"intent": "other", "keyword": ""}


def compose_reply(user_text, facts_text):
    """
    把真實查詢結果(facts_text)交給 LLM 組成白話、親切的繁體中文回覆。
    強調:只能用提供的數據,不可自行編造數字。
    """
    system = (
        "你是「ChargeAlert TW」充電站小幫手,用親切的繁體中文回覆使用者。\n"
        "重要規則:\n"
        "- 只能根據【查詢結果】裡的數字回答,絕對不可以自己編造或推測數量。\n"
        "- 回覆簡潔,2-4 句即可,可以用一點點 emoji(如 🔌⚡)但不要過多。\n"
        "- 狀態說明:空閒=可以去充、使用中=有人在用、離線=暫停服務。\n"
        "- AC 是慢充、DC 是快充。\n"
    )
    prompt = f"使用者問:{user_text}\n\n【查詢結果】\n{facts_text}\n\n請根據以上數據回覆使用者。"
    return _invoke(system, prompt, max_tokens=400)
