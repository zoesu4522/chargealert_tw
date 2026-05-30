import pymysql
import config


def get_connection():
    """建立 MySQL 連線"""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,  # 查詢結果用字典格式
    )


def test_connection():
    """測試能不能連到資料庫"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE();")
            result = cursor.fetchone()
            print(f" 成功連到資料庫:{result['DATABASE()']}")
        conn.close()
        return True
    except Exception as e:
        print(f" 連線失敗:{e}")
        return False


def upsert_connectors(connectors):
    """
    寫入/更新充電槍狀態,並偵測狀態變化
    connectors: 從 TDX 抓來的 LiveStatuses 陣列
    回傳:(寫入筆數, 變化筆數)
    """
    conn = get_connection()
    inserted = 0
    changes = 0
    change_list = []

    try:
        with conn.cursor() as cursor:
            for c in connectors:
                connector_id = c["ConnectorID"]
                new_status = c["ConnectorStatus"]

                # 1. 先查這支槍「之前」的狀態
                cursor.execute(
                    "SELECT current_status FROM connector_status WHERE connector_id = %s",
                    (connector_id,)
                )
                row = cursor.fetchone()
                old_status = row["current_status"] if row else None

                # 2. 如果狀態有變(且不是第一次寫入),記錄到歷史表
                if old_status is not None and old_status != new_status:
                    cursor.execute(
                        """INSERT INTO status_history
                           (connector_id, station_id, old_status, new_status)
                           VALUES (%s, %s, %s, %s)""",
                        (connector_id, c["StationID"], old_status, new_status)
                    )
                    changes += 1
                    # 收集變化詳情(給通知用)
                    change_list.append({
                        "connector_id": connector_id,
                        "station_id": c["StationID"],
                        "old_status": old_status,
                        "new_status": new_status,
                    })

                # 3. 寫入/更新即時狀態表(有就更新,沒有就新增)
                cursor.execute(
                    """INSERT INTO connector_status
                       (connector_id, station_id, charging_point_id,
                        connector_type, current_status, last_update_time)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                       current_status = VALUES(current_status),
                       last_update_time = VALUES(last_update_time)""",
                    (
                        connector_id,
                        c["StationID"],
                        c.get("ChargingPointID"),
                        c.get("ConnectorType"),
                        new_status,
                        c.get("LastUpdateTime"),
                    )
                )
                inserted += 1

        conn.commit()
        return inserted, changes, change_list

    except Exception as e:
        conn.rollback()
        print(f" 寫入失敗:{e}")
        return 0, 0, []
    finally:
        conn.close()

def upsert_stations(stations):
    conn = get_connection()
    count = 0
    skipped_coords = 0
    try:
        with conn.cursor() as cursor:
            for s in stations:
                # 組地址(從 Location.Address 的各部分拼起來)
                addr = ""
                loc = s.get("Location", {}).get("Address", {})
                if loc:
                    addr = f"{loc.get('City','')}{loc.get('Town','')}{loc.get('Road','')}{loc.get('No','')}"

                # 取座標 + 台灣經緯度範圍防呆(來源偶有異常值,超範圍就存 NULL,避免整批掛掉)
                lat = s.get("PositionLat")
                lon = s.get("PositionLon")
                if lat is None or not (20 <= lat <= 27):
                    lat = None
                    skipped_coords += 1
                if lon is None or not (118 <= lon <= 123):
                    lon = None

                cursor.execute(
                    """INSERT INTO station_info
                       (station_id, station_name, description, operator_id,
                        latitude, longitude, address, charging_rate,
                        parking_rate, service_time, telephone)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                       station_name = VALUES(station_name),
                       description = VALUES(description),
                       address = VALUES(address),
                       charging_rate = VALUES(charging_rate),
                       parking_rate = VALUES(parking_rate),
                       service_time = VALUES(service_time)""",
                    (
                        s["StationID"],
                        s.get("StationName", {}).get("Zh_tw", ""),
                        s.get("Description", ""),
                        s.get("OperatorID", ""),
                        lat,
                        lon,
                        addr,
                        s.get("ChargingRate", ""),
                        s.get("ParkingRate", ""),
                        s.get("ServiceTime", ""),
                        s.get("Telephone", ""),
                    )
                )
                count += 1
        conn.commit()
        if skipped_coords:
            print(f"  有 {skipped_coords} 個站座標異常或缺漏,已存為 NULL")
        return count
    except Exception as e:
        conn.rollback()
        print(f" 寫入充電站基本資料失敗:{e}")
        return 0
    finally:
        conn.close()

def get_station_info(station_id):
    """查詢單一充電站的基本資料(發通知時用)"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM station_info WHERE station_id = %s",
                (station_id,)
            )
            return cursor.fetchone()
    finally:
        conn.close()

# 充電槍類型分類(依據 IEC 62196 國際標準)
AC_TYPES = (1, 2, 3)   # J1772, Type2, Type3 → 交流 AC 慢充
DC_TYPES = (4, 5, 6)   # CHAdeMO, CCS, LEVDC → 直流 DC 快充


def get_station_stats(station_id):
    """
    查詢某充電站的統計:總數、AC/DC 的可用與總數
    回傳 dict
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT connector_type, current_status, COUNT(*) AS cnt
                   FROM connector_status
                   WHERE station_id = %s
                   GROUP BY connector_type, current_status""",
                (station_id,)
            )
            rows = cursor.fetchall()

        # 統計 AC / DC 的總數與可用數(status=1 為可用)
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
            if status == 1:
                stats["available"] += cnt

            if t in AC_TYPES:
                stats["ac_total"] += cnt
                if status == 1:
                    stats["ac_available"] += cnt
            elif t in DC_TYPES:
                stats["dc_total"] += cnt
                if status == 1:
                    stats["dc_available"] += cnt

        return stats
    finally:
        conn.close()

# ===== 測試:直接執行時,測連線 =====
if __name__ == "__main__":
    test_connection()