import time

# {user_id: 開始處理的 epoch 秒}
_processing = {}

# 逾時(秒):超過視為卡死,自動放行,避免某次例外沒清除導致該 user 永久被擋
BUSY_TIMEOUT_SECONDS = 30


def try_acquire(user_id):
    """
    原子地嘗試取得該 user 的處理鎖。
    回傳 True=搶到(可處理) / False=已被佔用(該擋下)。
    無 user_id 一律放行(回 True)。
    逾時的殘留鎖會被視為過期、可重新取得。
    注意:此函式內不得有 await,確保「檢查+設定」之間不被其他協程打斷。
    """
    if not user_id:
        return True
    now = time.time()
    started = _processing.get(user_id)
    if started is not None and (now - started) <= BUSY_TIMEOUT_SECONDS:
        return False  # 正在忙且未逾時 → 擋
    _processing[user_id] = now  # 搶到鎖(或接管逾時的殘留鎖)
    return True


def release(user_id):
    """處理完成後釋放鎖。"""
    if user_id:
        _processing.pop(user_id, None)


# 向後相容(若他處仍引用)
def is_busy(user_id):
    if not user_id:
        return False
    started = _processing.get(user_id)
    if started is None:
        return False
    if time.time() - started > BUSY_TIMEOUT_SECONDS:
        _processing.pop(user_id, None)
        return False
    return True


def mark_busy(user_id):
    if user_id:
        _processing[user_id] = time.time()


def clear(user_id):
    if user_id:
        _processing.pop(user_id, None)