import os
import json
import logging

logger = logging.getLogger("chargealert.bedrock")

# ── LLM 後端設定:優先 OpenAI,沒設定 key 才退回 Bedrock ──────────
# 設計:bedrock_client 對外介面(parse_intent / compose_reply)完全不變,
#       只在底層 _invoke 切換實際打哪個 LLM。OpenAI 配額即時可用,
#       不必等 Bedrock 配額審核;Bedrock 保留為後備,憑證/配額就緒時自動可用。

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Bedrock(後備)設定
REGION = "ap-northeast-1"
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

_USE_OPENAI = bool(OPENAI_API_KEY)

_openai_client = None
_bedrock_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _get_bedrock():
    global _bedrock_client
    if _bedrock_client is None:
        import boto3
        _bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)
    return _bedrock_client


def _invoke(system_prompt, user_text, max_tokens=400):
    """呼叫 LLM,回傳純文字。優先 OpenAI,否則 Bedrock。"""
    if _USE_OPENAI:
        client = _get_openai()
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    # 後備:Bedrock Converse API
    client = _get_bedrock()
    resp = client.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


# ── 意圖判斷:規則優先,LLM 後備 ──────────────────────────────
# 設計:核心查詢用確定性規則保證「一定能用」,不依賴 LLM 配額/憑證。
#       規則判斷不出來時,才用 LLM 增強(處理較模糊的自然語言)。
#       與 weather.py 的「規則 advisory」一致:事實層不綁 LLM。

_OVERALL_KEYWORDS = ("總共", "全部", "整體", "一共", "總數", "現在有多少", "多少充電", "概況", "全台", "所有")
_GREETING_KEYWORDS = ("你好", "哈囉", "嗨", "hi", "hello", "你是誰", "自我介紹", "怎麼用", "功能")
_STATION_SUFFIXES = ("有位子嗎", "有空位嗎", "有沒有位子", "有沒有空", "充電站", "充電", "的狀況", "狀況",
                     "有位嗎", "可以充嗎", "還有位子嗎", "在哪", "嗎", "呢", "?", "?")


def parse_intent_rule_based(user_text):
    """純關鍵字意圖判斷,不呼叫 LLM。回傳同 parse_intent 格式,或 None 表示規則拿不準。"""
    t = (user_text or "").strip()
    if not t:
        return {"intent": "other", "keyword": ""}

    if any(k in t for k in _OVERALL_KEYWORDS):
        return {"intent": "overall", "keyword": ""}

    if any(k in t for k in _GREETING_KEYWORDS) and len(t) <= 8:
        return {"intent": "other", "keyword": ""}

    keyword = t
    for suf in _STATION_SUFFIXES:
        keyword = keyword.replace(suf, "")
    keyword = keyword.strip()

    # 抽完仍含模糊詞(沒有明確地名)→ 規則拿不準,交給 LLM
    _VAGUE_WORDS = ("附近", "哪裡", "哪邊", "最近", "我家", "這附近", "周圍", "周邊")
    if keyword and any(v in keyword for v in _VAGUE_WORDS):
        return None

    # 抽完仍像「句子」(含贅字)→ 規則太貪心會誤判,交給 LLM 乾淨抽取
    _FILLER_WORDS = ("幫我", "幫忙", "看看", "請問", "我想", "我要", "想找", "想查",
                     "那邊", "這邊", "那裡", "現在", "一下", "麻煩", "可以幫")
    if keyword and any(f in keyword for f in _FILLER_WORDS):
        return None

    if keyword:
        return {"intent": "station", "keyword": keyword}
    return None


def parse_intent(user_text):
    """
    意圖分類。回傳 {"intent": "overall"|"station"|"other", "keyword": "..."}。
    流程:先規則判斷;規則明確就用。規則拿不準(None)時,LLM 可用就用,
          LLM 失敗(配額 / 憑證 / 任何錯)則安全退回 other。
    """
    rule = parse_intent_rule_based(user_text)
    if rule is not None:
        return rule

    system = (
        "你是一個意圖分類器,專門處理電動車充電站查詢。"
        "使用者會用中文問問題。請判斷意圖並只回傳 JSON,不要任何其他文字、不要 markdown。\n"
        "格式:{\"intent\": \"overall\" 或 \"station\" 或 \"other\", \"keyword\": \"地名或站名,沒有就空字串\"}\n"
        "規則:\n"
        "- 問整體、全部、總共、現在有多少可用、概況 -> overall\n"
        "- 問某個具體地點或店名(例如「中壢有位子嗎」「江園門市」)-> station,keyword 放那個地名\n"
        "- 打招呼、自我介紹、無關問題 -> other\n"
        "keyword 要求:\n"
        "- 只放「地名或店名本身」,去掉所有贅字(幫我、看看、那邊、現在、有沒有位子、嗎…)。\n"
        "  例如「幫我看看中壢國小那邊有沒有位子」-> keyword 放「中壢」;「台茂現在有位子嗎」-> keyword 放「台茂」。\n"
        "- 若是學校、公園、地標等不是充電站名稱的地點,改放它所在的行政區或地名(例如「中壢國小」->「中壢」)。\n"
    )
    try:
        raw = _invoke(system, user_text, max_tokens=120)
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        intent = data.get("intent", "other")
        keyword = data.get("keyword", "") or ""
        if intent not in ("overall", "station", "other"):
            intent = "other"
        return {"intent": intent, "keyword": keyword.strip()}
    except Exception as e:
        logger.warning("LLM 意圖解析失敗,fallback other: %s", e)
        return {"intent": "other", "keyword": ""}


def compose_reply(user_text, facts_text):
    system = (
        "你是「ChargeAlert TW」充電站小幫手,用親切的繁體中文回覆使用者。\n"
        "重要規則:\n"
        "- 只能根據【查詢結果】裡的數字回答,絕對不可以自己編造或推測數量。\n"
        "- 你只負責充電站相關問題。若使用者問與充電站無關的內容(如寫詩、聊天、其他領域問題),"
        "禮貌說明你是充電站小幫手,只能協助查詢充電站,不要回答無關內容。\n"
        "- 回覆簡潔,2-4 句即可,可以用一點點 emoji(如 🔌⚡)但不要過多。\n"
        "- 狀態說明:空閒=可以去充、使用中=有人在用、離線=暫停服務。\n"
        "- AC 是慢充、DC 是快充。\n"
    )
    prompt = f"使用者問:{user_text}\n\n【查詢結果】\n{facts_text}\n\n請根據以上數據回覆使用者。"
    return _invoke(system, prompt, max_tokens=400)