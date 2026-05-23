
from apscheduler.schedulers.blocking import BlockingScheduler
from fetch_and_save import run_once
import config

# 抓取間隔(分鐘)
INTERVAL_MINUTES = 15


def job():
    """排程要執行的工作"""
    try:
        run_once(city=config.TARGET_CITY)
    except Exception as e:
        print(f" 排程執行出錯:{e}")


if __name__ == "__main__":
    print("=" * 50)
    print(f" ChargeAlert TW 自動巡邏啟動")
    print(f"   每 {INTERVAL_MINUTES} 分鐘自動抓取一次")
    print(f"   目標縣市:{config.TARGET_CITY}")
    print(f"   按 Ctrl+C 可停止")
    print("=" * 50)

    print("\n▶️  立即執行第一次...")
    job()

    scheduler = BlockingScheduler(timezone="Asia/Taipei")
    scheduler.add_job(job, "interval", minutes=INTERVAL_MINUTES)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n 已停止自動巡邏")