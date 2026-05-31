
import os
import pymysql

# 充電槍類型分類(依 IEC 62196 國際標準,與 scraper 的 db.py 一致)
AC_TYPES = (1, 2, 3)   # J1772, Type2, Type3 -> 交流 AC 慢充
DC_TYPES = (4, 5, 6)   # CHAdeMO, CCS, LEVDC -> 直流 DC 快充

#狀態:1=空閒可用、2=使用中、3=離線
STATUS_AVAILABLE = 1


def get_connection():
    """建立 MySQL 連線。charset 一定要 utf8mb4,中文才不會變問號。"""
    return pymysql.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _summarize(rows):
    """把 (connector_type, current_status, cnt) 的列表彙整成 AC/DC 統計 dict。"""
    stats = {
        "ac_total": 0, "ac_available": 0,
        "dc_total": 0, "dc_available": 0,
        "total": 0, "available": 0,
    }
    for r in rows:
        t = r["connector_type"]
        status = r["current_status"]
        cnt = r["cnt"]

        stats["total"] += cnt
        if status == STATUS_AVAILABLE:
            stats["available"] += cnt

        if t in AC_TYPES:
            stats["ac_total"] += cnt
            if status == STATUS_AVAILABLE:
                stats["ac_available"] += cnt
        elif t in DC_TYPES:
            stats["dc_total"] += cnt
            if status == STATUS_AVAILABLE:
                stats["dc_available"] += cnt
    return stats


def get_overall_stats():
    """
    整體統計:目前監測的「所有」充電站的可用概況。
    刻意不寫死縣市 —— 之後擴充到其他地區,這個查詢自動涵蓋,不用改程式。
    回傳:含 station_count 的統計 dict。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT connector_type, current_status, COUNT(*) AS cnt
                   FROM connector_status
                   GROUP BY connector_type, current_status"""
            )
            rows = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(DISTINCT station_id) AS c FROM connector_status"
            )
            station_count = cursor.fetchone()["c"]

        stats = _summarize(rows)
        stats["station_count"] = station_count
        return stats
    finally:
        conn.close()


def search_stations_by_name(keyword, limit=5):
    """
    用站名模糊比對找充電站(使用者多半打地名/店名,不會知道 station_id)。
    回傳 [{station_id, station_name, address}, ...],最多 limit 筆。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT station_id, station_name, address
                   FROM station_info
                   WHERE station_name LIKE %s
                   LIMIT %s""",
                (f"%{keyword}%", limit),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_station_stats(station_id):
    """
    單站統計:某站的 AC/DC 可用與總數。沿用 scraper 同樣的算法。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT connector_type, current_status, COUNT(*) AS cnt
                   FROM connector_status
                   WHERE station_id = %s
                   GROUP BY connector_type, current_status""",
                (station_id,),
            )
            rows = cursor.fetchall()
        return _summarize(rows)
    finally:
        conn.close()

# ===== 以下為後台儀表板用的查詢 =====

# 狀態碼對照:1=空閒、2=使用中、3=離線
STATUS_LABELS = {1: "空閒", 2: "使用中", 3: "離線"}


def get_status_distribution():
    """
    狀態分布:各狀態(空閒/使用中/離線)各有幾支槍。
    回傳 [{"status": 1, "label": "空閒", "count": 1128}, ...]
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT current_status, COUNT(*) AS cnt
                   FROM connector_status
                   GROUP BY current_status
                   ORDER BY current_status"""
            )
            rows = cursor.fetchall()
        return [
            {
                "status": r["current_status"],
                "label": STATUS_LABELS.get(r["current_status"], "其他"),
                "count": r["cnt"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_top_available_stations(limit=10):
    """
    可用槍數最多的站排名(Top N)。給儀表板的橫條圖用。
    available = 該站 current_status=1 的槍數;total = 該站總槍數。
    回傳 [{"station_name", "available", "total"}, ...] 依 available 由多到少。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT s.station_name AS station_name,
                          SUM(CASE WHEN c.current_status = 1 THEN 1 ELSE 0 END) AS available,
                          COUNT(*) AS total
                   FROM connector_status c
                   JOIN station_info s ON c.station_id = s.station_id
                   GROUP BY c.station_id, s.station_name
                   ORDER BY available DESC
                   LIMIT %s""",
                (limit,),
            )
            rows = cursor.fetchall()
        # SUM 回傳的是 Decimal,轉成 int 方便前端用
        return [
            {
                "station_name": r["station_name"],
                "available": int(r["available"]),
                "total": int(r["total"]),
            }
            for r in rows
        ]
    finally:
        conn.close()

#可用量曲線:最近 N 小時的快照時間序列,給趨勢圖用。
#power_type: 'ALL' / 'AC' / 'DC'。回傳時間由舊到新。
def get_history(hours=24, power_type="ALL"):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT snapshot_at, total, available, in_use, offline
                   FROM availability_snapshot
                   WHERE power_type = %s
                     AND snapshot_at >= NOW() - INTERVAL %s HOUR
                   ORDER BY snapshot_at ASC""",
                (power_type, hours),
            )
            rows = cursor.fetchall()
        return [
            {
                "t": r["snapshot_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "total": r["total"],
                "available": r["available"],
                "in_use": r["in_use"],
                "offline": r["offline"],
            }
            for r in rows
        ]
    finally:
        conn.close()