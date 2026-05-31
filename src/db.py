import pymysql
import config

#建立 SQL 連線
def get_connection():
    
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,  
    )

#測試
def test_connection():
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
  
    conn = get_connection()
    inserted = 0
    changes = 0
    change_list = []

    try:
        with conn.cursor() as cursor:
            for c in connectors:
                connector_id = c["ConnectorID"]
                new_status = c["ConnectorStatus"]

                #先查「之前」的狀態
                cursor.execute(
                    "SELECT current_status FROM connector_status WHERE connector_id = %s",
                    (connector_id,)
                )
                row = cursor.fetchone()
                old_status = row["current_status"] if row else None

                #如果狀態有變(且不是第一次寫入),記錄到歷史表
                if old_status is not None and old_status != new_status:
                    cursor.execute(
                        """INSERT INTO status_history
                           (connector_id, station_id, old_status, new_status)
                           VALUES (%s, %s, %s, %s)""",
                        (connector_id, c["StationID"], old_status, new_status)
                    )
                    changes += 1
                    change_list.append({
                        "connector_id": connector_id,
                        "station_id": c["StationID"],
                        "old_status": old_status,
                        "new_status": new_status,
                    })

                #寫入/更新即時狀態表(有就更新,沒有就新增)
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

def upsert_stations(stations, city="Taoyuan"):
    """
    寫入/更新充電站基本資料。
    city:此批站資料所屬縣市的英文 code(例 "Taoyuan"),呼叫端傳入。
    district:從 TDX 地址的 Town 欄位取得(中文,例「中壢區」)。
    """
    conn = get_connection()
    count = 0
    skipped_coords = 0
    try:
        with conn.cursor() as cursor:
            for s in stations:
                #組地址(從Location.Address 的各部分拼起來)
                addr = ""
                district = None
                loc = s.get("Location", {}).get("Address", {})
                if loc:
                    addr = f"{loc.get('City','')}{loc.get('Town','')}{loc.get('Road','')}{loc.get('No','')}"
                    #區直接取 TDX 的 Town(比從 address 字串抽乾淨)
                    town = loc.get("Town")
                    if town:
                        district = town

                #取座標+台灣經緯度範圍防呆(來源偶有異常值,超範圍就存 NULL,避免整批掛掉)
                lat = s.get("PositionLat")
                lon = s.get("PositionLon")
                if lat is None or not (20 <= lat <= 27):
                    lat = None
                    skipped_coords += 1
                if lon is None or not (118 <= lon <= 123):
                    lon = None

                cursor.execute(
                    """INSERT INTO station_info
                       (station_id, station_name, city, district, description,
                        operator_id, latitude, longitude, address, charging_rate,
                        parking_rate, service_time, telephone)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                       station_name = VALUES(station_name),
                       city = VALUES(city),
                       district = VALUES(district),
                       description = VALUES(description),
                       address = VALUES(address),
                       charging_rate = VALUES(charging_rate),
                       parking_rate = VALUES(parking_rate),
                       service_time = VALUES(service_time)""",
                    (
                        s["StationID"],
                        s.get("StationName", {}).get("Zh_tw", ""),
                        city,
                        district,
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

#查詢單一充電站的基本資料(發通知時用)

def get_station_info(station_id):
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

#充電槍類型分類(依據 IEC 62196 國際標準)
AC_TYPES = (1, 2, 3)   # J1772, Type2, Type3 → 交流 AC 慢充
DC_TYPES = (4, 5, 6)   # CHAdeMO, CCS, LEVDC → 直流 DC 快充

#查詢某充電站的統計:總數、AC/DC 的可用與總數 回傳 dict
def get_station_stats(station_id):
    
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

        #統計AC / DC的總數與可用數(status=1為可用)
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

#對目前 connector_status 做一次彙總快照,寫進 availability_snapshot。
#每次爬蟲輪詢(upsert_connectors)之後呼叫一次,趨勢圖才有時間序列可畫。
#一次寫 3 列:ALL / AC / DC。狀態碼 1=空閒 2=使用中 3=離線。
def insert_snapshot():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            #用DB時間,讓3列共用同一個timestamp,且與status_history 一致
            cursor.execute("SELECT NOW() AS now")
            now = cursor.fetchone()["now"]

            cursor.execute(
                """SELECT connector_type, current_status, COUNT(*) AS cnt
                   FROM connector_status
                   GROUP BY connector_type, current_status"""
            )
            rows = cursor.fetchall()

            buckets = {
                "ALL": {"total": 0, "available": 0, "in_use": 0, "offline": 0},
                "AC":  {"total": 0, "available": 0, "in_use": 0, "offline": 0},
                "DC":  {"total": 0, "available": 0, "in_use": 0, "offline": 0},
            }

            def add(b, status, cnt):
                b["total"] += cnt
                if status == 1:
                    b["available"] += cnt
                elif status == 2:
                    b["in_use"] += cnt
                elif status == 3:
                    b["offline"] += cnt

            for r in rows:
                t, status, cnt = r["connector_type"], r["current_status"], r["cnt"]
                add(buckets["ALL"], status, cnt)
                if t in AC_TYPES:
                    add(buckets["AC"], status, cnt)
                elif t in DC_TYPES:
                    add(buckets["DC"], status, cnt)

            for power_type, b in buckets.items():
                cursor.execute(
                    """INSERT INTO availability_snapshot
                       (snapshot_at, power_type, total, available, in_use, offline)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (now, power_type, b["total"], b["available"], b["in_use"], b["offline"]),
                )
        conn.commit()
        print(f" 快照寫入完成:ALL 可用 {buckets['ALL']['available']}/{buckets['ALL']['total']}")
        return True
    except Exception as e:
        conn.rollback()
        print(f" 寫入快照失敗:{e}")
        return False
    finally:
        conn.close()

#測連線 
if __name__ == "__main__":
    test_connection()