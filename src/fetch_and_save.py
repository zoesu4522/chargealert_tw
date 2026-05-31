import notifier
import requests
import config
from tdx_client import get_tdx_token
import db
from datetime import datetime


def fetch_live_status(city="Taoyuan"):
    """抓取指定縣市的全部充電槍即時狀態"""
    token = get_tdx_token()
    if not token:
        return None

    url = f"{config.TDX_API_BASE}{config.EV_LIVE_STATUS_PATH}/{city}"
    params = {"$format": "JSON"}
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        print(f" 抓取 {city} 充電槍即時狀態...")
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        statuses = data.get("LiveStatuses", [])
        print(f" 抓到 {len(statuses)} 支充電槍")
        return statuses
    except requests.exceptions.RequestException as e:
        print(f" 抓取失敗:{e}")
        return None


def run_once(city="Taoyuan"):
    """執行一次完整流程:抓資料 → 寫入 → 記錄"""
    print("=" * 50)
    print(f" 開始- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    conn = db.get_connection()
    run_id = None
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO scrape_runs (status) VALUES ('running')"
            )
            run_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    #抓資料
    statuses = fetch_live_status(city)

    if statuses is None:
        _finish_run(run_id, 0, 0, "error", "抓取失敗")
        return

    inserted, changes, change_list = db.upsert_connectors(statuses)
    db.insert_snapshot()
    print(f"💾 寫入 {inserted} 支,偵測到 {changes} 筆狀態變化")

    if change_list:
        notified = notifier.notify_available(change_list)
        if notified > 0:
            print(f"📱 已推播 {notified} 個空位通知")

    _finish_run(run_id, inserted, changes, "ok", None)

    print("=" * 50)
    print(" 完成!")
    print("=" * 50)


def _finish_run(run_id, count, changes, status, error):
    """更新執行紀錄的結果"""
    if run_id is None:
        return
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE scrape_runs
                   SET finished_at = NOW(), connectors_count = %s,
                       changes_count = %s, status = %s, error_message = %s
                   WHERE id = %s""",
                (count, changes, status, error, run_id)
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    run_once(city="Taoyuan")