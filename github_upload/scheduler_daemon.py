import time
import json
import argparse
import schedule
from datetime import datetime
from config import SCHEDULE_TIME, REFRESH_INTERVAL_MINUTES, LATEST_REPORT_PATH, HISTORY_REPORT_PATH
from data_service import MacroDataService
from ai_translator import AITranslator
from notifier import send_desktop_notification


def run_daily_macro_pipeline(send_notification: bool = True):
    """
    全自動資料流水線 (支援定時與每 5 分鐘高頻刷新)：
    1. 抓取 World Monitor、台灣總經、工研院趨勢、永豐金證券 Shioaji 台股即時行情
    2. 執行超跌量化篩選與跨維度共振判定
    3. 產出通俗繁體中文戰報
    4. 寫入本地快取 JSON 檔案
    5. 發送 Windows 桌面彈窗通知 (可依排程決定是否彈出)
    """
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now_str}] 正在執行數據資料同步更新 (每 {REFRESH_INTERVAL_MINUTES} 分鐘自動更新)...")

    # 1. 抓取整合資料
    data_svc = MacroDataService()
    aggregated_data = data_svc.aggregate_full_report_data()

    # 2. 轉譯白話文與跨維度共振
    translator = AITranslator()
    report = translator.generate_colloquial_report(aggregated_data)

    # 3. 儲存最新戰報
    with open(LATEST_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[檔案儲存] 最新戰報已儲存至: {LATEST_REPORT_PATH}")

    # 更新歷史紀錄
    try:
        history = []
        if HISTORY_REPORT_PATH.exists():
            with open(HISTORY_REPORT_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.append({
            "timestamp": report["summary_date"],
            "score": aggregated_data["world_monitor"]["overall_score"],
            "rating": aggregated_data["world_monitor"]["overall_rating"]
        })
        history = history[-60:]
        with open(HISTORY_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[歷史記錄警告] 無法寫入歷史紀錄: {e}")

    # 4. 發送系統桌面彈窗推播
    if send_notification:
        wm = aggregated_data["world_monitor"]
        score = wm.get("overall_score", 0)
        rating = wm.get("overall_rating", "NEUTRAL")
        title = f"🌐【今日全球總經 × 永豐金台股戰報】"
        message = f"評級：{rating} (信心: {score}分)\n發現 {len(report.get('turnaround_radar', {}).get('stocks', []))} 檔中小型超跌轉機股！點擊開啟戰情室！"
        send_desktop_notification(title=title, message=message)

    print(f"[{now_str}] 數據資料更新完成！\n")
    return report


def start_scheduler():
    """啟動排程守護程序 (Daemon)"""
    print("=" * 65)
    print(f"⏰ 全球總經 × 永豐金台股情報戰情室 - 背景排程守護進程已啟動")
    print(f"🔄 數據自動更新頻率: 每 {REFRESH_INTERVAL_MINUTES} 分鐘自動更新一次")
    print(f"📢 每日戰報彈窗推播: {SCHEDULE_TIME}")
    print(f"💡 隨時按 Ctrl+C 可停止服務")
    print("=" * 65)

    # 首次啟動時立即執行一次
    print("\n[初始化] 正在執行首次數據抓取...")
    run_daily_macro_pipeline(send_notification=False)

    # 1. 每 1 分鐘高頻背景即時同步數據與地緣戰報 (不彈出重複推播打擾工作)
    schedule.every(REFRESH_INTERVAL_MINUTES).minutes.do(run_daily_macro_pipeline, send_notification=False)

    # 2. 每日 08:30 發送早報桌面彈窗通知
    schedule.every().day.at(SCHEDULE_TIME).do(run_daily_macro_pipeline, send_notification=True)

    while True:
        schedule.run_pending()
        time.sleep(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="總經情報定時排程服務")
    parser.add_argument("--now", action="store_true", help="立即執行一次資料更新與推播後退出")
    args = parser.parse_args()

    if args.now:
        run_daily_macro_pipeline(send_notification=True)
    else:
        start_scheduler()
