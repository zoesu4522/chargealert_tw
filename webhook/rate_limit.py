"""
rate_limit.py — 簡易「處理中」防連點(per-user)。

用途:使用者點查詢後,On-Demand 抓取需 1-2 秒,這段時間重複點會跳多張重複卡。
做法:記錄「處理中的 user_id + 時間戳」,處理完成前再點就擋下。
限制:記憶體版,僅適用單 worker(本專案 uvicorn 預設單進程)。多 worker 需改用 Redis。

用法:
    import rate_limit
    if rate_limit.is_busy(user_id):
        return {"type": "text", "text": "⏳ 正在查詢中,請稍候…"}
    rate_limit.mark_busy(user_id)
    try:
        ... 處理 ...
    finally:
        rate_limit.clear(user_id)
"""

import time

# {user_id: 開始處理的 epoch 秒}
_processing = {}

# 逾時(秒):超過視為卡死,自動放行,避免某次例外沒清除導致該 user 永久被擋
BUSY_TIMEOUT_SECONDS = 30


def is_busy(user_id):
    """該 user 是否正在處理中(且未逾時)。無 user_id 一律放行。"""
    if not user_id:
        return False
    started = _processing.get(user_id)
    if started is None:
        return False
    if time.time() - started > BUSY_TIMEOUT_SECONDS:
        # 逾時的殘留標記,清掉並放行
        _processing.pop(user_id, None)
        return False
    return True


def mark_busy(user_id):
    if user_id:
        _processing[user_id] = time.time()


def clear(user_id):
    if user_id:
        _processing.pop(user_id, None)
