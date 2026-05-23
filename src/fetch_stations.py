import requests
import config
from tdx_client import get_tdx_token
import db


def fetch_and_save_stations(city="Taoyuan"):
    token = get_tdx_token()
    if not token:
        return

    url = f"{config.TDX_API_BASE}/v1/EV/Station/City/{city}"
    params = {"$format": "JSON"}
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
    }

    print(f"📡 抓取 {city} 充電站基本資料...")
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    stations = data.get("Stations", [])
    print(f"✅ 抓到 {len(stations)} 個充電站")

    count = db.upsert_stations(stations)
    print(f"💾 寫入 {count} 個充電站基本資料")


if __name__ == "__main__":
    fetch_and_save_stations("Taoyuan")