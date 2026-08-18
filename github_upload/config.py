import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# 台灣標準時區 (Asia/Taipei, UTC+8)
TW_TZ = timezone(timedelta(hours=8))

def get_tw_now() -> datetime:
    """取得台灣標準時間 (UTC+8)"""
    return datetime.now(TW_TZ)

def get_tw_now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """取得台灣標準時間字串 (UTC+8)"""
    return datetime.now(TW_TZ).strftime(fmt)

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 最新戰報存檔路徑
LATEST_REPORT_PATH = DATA_DIR / "latest_macro_report.json"
HISTORY_REPORT_PATH = DATA_DIR / "report_history.json"

# 排程設定 (預設每日 08:30 發送早報，且每 1 分鐘高頻自動刷新數據與地緣戰報)
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "08:30")
REFRESH_INTERVAL_MINUTES = int(os.getenv("REFRESH_INTERVAL_MINUTES", "1"))

# 永豐金證券 (SinoPac Shioaji API) 金鑰與憑證設定
SHIOAJI_API_KEY = os.getenv("SHIOAJI_API_KEY", "")
SHIOAJI_SECRET_KEY = os.getenv("SHIOAJI_SECRET_KEY", "")
SHIOAJI_SIMULATION = os.getenv("SHIOAJI_SIMULATION", "False").lower() in ["true", "1", "yes"]
SHIOAJI_CA_PATH = os.getenv("SHIOAJI_CA_PATH", r"C:\Users\aichi\Downloads\Sinopac.pfx")
SHIOAJI_CA_PASSWD = os.getenv("SHIOAJI_CA_PASSWD", "")
SHIOAJI_PERSON_ID = os.getenv("SHIOAJI_PERSON_ID", "")

# 其他第三方 API 設定 (選填)
WORLD_MONITOR_API_URL = os.getenv("WORLD_MONITOR_API_URL", "")
WORLD_MONITOR_API_KEY = os.getenv("WORLD_MONITOR_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 儀表板與安全存取通行碼
APP_PASSWORD = os.getenv("APP_PASSWORD", "a7883310")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8501"))
DASHBOARD_URL = f"http://localhost:{DASHBOARD_PORT}"
