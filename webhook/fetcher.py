
import os
import threading

import requests
from cachetools import TTLCache

import db  # webhook/db.py(共用同一個 get_connection)
from tdx_client import get_tdx_token

TDX_API_BASE = "https://tdx.transportdata.tw/api/basic"
EV_STATION_PATH = "/v1/EV/Station/City"          # 站基本資料
EV_LIVE_STATUS_PATH = "/v1/EV/ConnectorLiveStatus/City"  # 槍即時狀態

# 10 分鐘快取,最多放 30 個縣市
_cache = TTLCache(maxsize=30, ttl=600)
_lock = threading.Lock()


def _tdx_get(token, path, city):
    """共用的 TDX GET:回傳 JSON dict;失敗回 None。"""
    url = f"{TDX_API_BASE}{path}/{city}"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, params={"$format": "JSON"}, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f" TDX 抓取失敗({path}/{city}):{e}")
        return None


def _upsert_stations(stations, city):
    """寫入站基本資料(含 city/district)。精簡版,僅 On-Demand 用。"""
    conn = db.get_connection()
    count = 0
    try:
        with conn.cursor() as cursor:
            for s in stations:
                addr = ""
                district = None
                loc = s.get("Location", {}).get("Address", {})
                if loc:
                    addr = f"{loc.get('City','')}{loc.get('Town','')}{loc.get('Road','')}{loc.get('No','')}"
                    town = loc.get("Town")
                    if town:
                        district = town

                lat = s.get("PositionLat")
                lon = s.get("PositionLon")
                if lat is None or not (20 <= lat <= 27):
                    lat = None
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
                    ),
                )
                count += 1
        conn.commit()
        return count
    except Exception as e:
        conn.rollback()
        print(f" 寫入站資料失敗:{e}")
        return 0
    finally:
        conn.close()


def _upsert_connectors(connectors):
    """寫入槍即時狀態。精簡版(On-Demand 不記 status_history,只更新現況)。"""
    conn = db.get_connection()
    count = 0
    try:
        with conn.cursor() as cursor:
            for c in connectors:
                cursor.execute(
                    """INSERT INTO connector_status
                       (connector_id, station_id, charging_point_id,
                        connector_type, current_status, last_update_time)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                       current_status = VALUES(current_status),
                       last_update_time = VALUES(last_update_time)""",
                    (
                        c["ConnectorID"],
                        c["StationID"],
                        c.get("ChargingPointID"),
                        c.get("ConnectorType"),
                        c["ConnectorStatus"],
                        c.get("LastUpdateTime"),
                    ),
                )
                count += 1
        conn.commit()
        return count
    except Exception as e:
        conn.rollback()
        print(f" 寫入槍狀態失敗:{e}")
        return 0
    finally:
        conn.close()


def fetch_city_on_demand(city):
    """
    On-Demand 抓某縣市(站+槍),寫 DB。回傳 db.get_city_stats(city) 的統計 dict。
    成功會快取 10 分鐘;期間重複呼叫直接回快取,不重打 TDX。
    失敗回 {"error": "...", "message": "..."},呼叫端據此給友善訊息。
    """
    if city in _cache:
        return _cache[city]

    with _lock:
        # 並發保護:拿到鎖後再檢查一次(可能別的 thread 剛抓完)
        if city in _cache:
            return _cache[city]

        token = get_tdx_token()
        if not token:
            return {"error": "TDX_AUTH", "message": "服務暫時忙碌,請稍後再試"}

        # 1) 抓站基本資料
        station_data = _tdx_get(token, EV_STATION_PATH, city)
        if station_data is None:
            return {"error": "TDX_FAIL", "message": "查詢服務忙碌,請稍後再試"}
        stations = station_data.get("Stations", [])
        if not stations:
            return {"error": "NO_CITY", "message": "查無此縣市的充電站資料"}
        _upsert_stations(stations, city)

        # 2) 抓槍即時狀態
        got_connectors = 0
        live_data = _tdx_get(token, EV_LIVE_STATUS_PATH, city)
        if live_data is not None:
            statuses = live_data.get("LiveStatuses", [])
            got_connectors = len(statuses)
            _upsert_connectors(statuses)

        # 3) 從 DB 算統計回傳
        stats = db.get_city_stats(city)
        # 只在「這次有抓到槍、且統計有資料」時才快取;
        # 否則(槍 API 偶發回空 / total=0)不快取,讓下次查詢能重試,
        # 避免把 total:0 卡在快取 10 分鐘。
        if got_connectors > 0 and stats.get("total", 0) > 0:
            _cache[city] = stats
        else:
            print(f"  {city} 槍資料為空(got={got_connectors}),不快取,下次重試")
        return stats