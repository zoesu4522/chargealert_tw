
import time

# {user_id: 上次取得鎖的 epoch 秒}
_last_acquired = {}

# 冷卻秒數:按一次後,這段時間內的重複點都擋
COOLDOWN_SECONDS = 3


def try_acquire(user_id):
 
    if not user_id:
        return True
    now = time.time()
    last = _last_acquired.get(user_id)
    if last is not None and (now - last) < COOLDOWN_SECONDS:
        return False  # 冷卻期內 → 擋
    _last_acquired[user_id] = now  # 放行並記錄時間
    return True


def release(user_id):
    """冷卻式不需要主動釋放(時間到自然過期)。保留空函式以相容呼叫端。"""
    pass


def _cleanup(max_entries=10000):
    """選擇性:避免 _last_acquired 無限增長。超過上限時清掉過期項。"""
    if len(_last_acquired) < max_entries:
        return
    now = time.time()
    for uid in [u for u, t in _last_acquired.items() if now - t > COOLDOWN_SECONDS]:
        _last_acquired.pop(uid, None)