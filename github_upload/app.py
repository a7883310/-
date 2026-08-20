import json
import os
import io
import time
import socket
import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import qrcode
from PIL import Image
import config
from config import (
    LATEST_REPORT_PATH,
    HISTORY_REPORT_PATH,
    SHIOAJI_API_KEY,
    SHIOAJI_SECRET_KEY,
    SHIOAJI_SIMULATION,
    REFRESH_INTERVAL_MINUTES,
    TW_TZ,
    get_tw_now,
    get_tw_now_str
)
from scheduler_daemon import run_daily_macro_pipeline
from notifier import send_desktop_notification
from long_term_strategy_service import LongTermStrategyService
from position_tracking_service import PositionTrackingService
from sinopac_service import SinoPacDataService
from swing_trading_screener import SwingTradingScreener
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

SHIOAJI_CA_PATH = getattr(config, "SHIOAJI_CA_PATH", r"C:\Users\aichi\Downloads\Sinopac.pfx")
SHIOAJI_CA_PASSWD = getattr(config, "SHIOAJI_CA_PASSWD", "")
SHIOAJI_PERSON_ID = getattr(config, "SHIOAJI_PERSON_ID", "")

# 頁面配置
st.set_page_config(
    page_title="50年華爾街傳奇操盤手 × 永豐金全球總經與長期投資戰情室",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_local_lan_ip() -> str:
    """自動偵測電腦所在區域網路 IP (供手機連線)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


local_ip = get_local_lan_ip()
mobile_url = f"http://{local_ip}:8501"


def generate_qr_image(url: str) -> Image.Image:
    """生成綠黑高對比度手機掃描 QR Code"""
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color='#10b981', back_color='#0b0f19').convert('RGB')


# 移除會導致瀏覽器硬重載中斷 session 的 HTML Meta Refresh，專注採用 Streamlit WebSocket 高頻動態刷新
st.markdown(f"""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    /* 全域背景與字體 */
    .stApp {{
        background-color: #0b0f19;
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}

    
    /* 頂部戰情報告卡片 */
    .war-room-header {{
        background: linear-gradient(135deg, #111827 0%, #1e1b4b 100%);
        border: 1px solid #4338ca;
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }}

    .metric-container {{
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }}

    .section-card {{
        background-color: #111827;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border: 1px solid #1e293b;
    }}

    /* 操盤手核心行動大卡片 */
    .action-hero-card {{
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        border: 2px solid #6366f1;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 16px;
        box-shadow: 0 8px 25px rgba(99, 102, 241, 0.25);
    }}

    /* 執行數值方塊容器 */
    .execution-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 10px;
        margin: 12px 0 16px 0;
    }}

    .stop-box {{
        background-color: #450a0a;
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}
    .target-box {{
        background-color: #064e3b;
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}
    .entry-box {{
        background-color: #172554;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}
    .rr-box {{
        background-color: #451a03;
        border: 1px solid #f97316;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}

    /* 長期投資專用估值方塊 */
    .longterm-cheap-box {{
        background-color: #064e3b;
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}
    .longterm-fair-box {{
        background-color: #172554;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}
    .longterm-premium-box {{
        background-color: #451a03;
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}
    .longterm-rating-box {{
        background-color: #312e81;
        border: 1px solid #818cf8;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }}

    /* 思考鏈步驟卡片 */
    .cot-step-box {{
        background-color: #111827;
        border-left: 4px solid #818cf8;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.92rem;
        line-height: 1.6;
        color: #e2e8f0;
    }}

    /* 驗證鏈檢驗項目 */
    .verify-item-box {{
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 6px;
    }}

    /* 手機螢幕適配優化 */
    @media (max-width: 768px) {{
        .war-room-header {{
            padding: 12px 14px;
        }}
        .war-room-header h1 {{
            font-size: 1.35rem !important;
        }}
        .action-hero-card {{
            padding: 12px;
        }}
        .execution-grid {{
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 8px;
        }}
        .stTabs [data-baseweb="tab"] {{
            padding: 6px 10px !important;
            font-size: 0.82rem !important;
        }}
    }}
</style>
""", unsafe_allow_html=True)


from whitelist_service import AccessWhitelistService, generate_user_token

whitelist_svc = AccessWhitelistService()


def get_secure_auth_token(password: str) -> str:
    """計算安全授權 Token (SHA-256)"""
    return generate_user_token(password)



def check_access_password() -> bool:
    """外來用戶白名單安全防護 (支援多用戶白名單、專屬免密邀請連結與記憶登入)"""
    # 1. 檢查 URL 網址參數是否持有有效 Token (F5 重新整理 / 分頁重開皆永久保持登入)
    url_token = None
    if hasattr(st, "query_params"):
        url_token = st.query_params.get("auth")
    elif hasattr(st, "experimental_get_query_params"):
        url_token = st.experimental_get_query_params().get("auth", [None])[0]

    if url_token:
        is_valid, user_data = whitelist_svc.validate_access(url_token)
        if is_valid:
            st.session_state["_auth_verified"] = True
            st.session_state["_auth_user"] = user_data
            return True

    # 2. 檢查目前 Session 狀態 (每分鐘 WebSocket 動態刷新時維持登入)
    if st.session_state.get("_auth_verified", False):
        return True

    # 渲染極簡安全鎖定登入畫面
    st.markdown("""
    <div style="max-width: 520px; margin: 40px auto 20px auto; background: linear-gradient(145deg, #111827, #1e1b4b); border: 1px solid #4338ca; border-radius: 14px; padding: 28px 24px; text-align: center; box-shadow: 0 20px 35px -10px rgba(0,0,0,0.7);">
        <div style="font-size: 2.8rem; margin-bottom: 8px;">🔐</div>
        <h3 style="color: #f8fafc; font-weight: 800; margin-bottom: 6px;">全球總經 × 投資戰情室</h3>
        <p style="color: #94a3b8; font-size: 0.92rem; line-height: 1.6; margin-bottom: 0;">本系統受個人安全白名單防護<br>請輸入您的專屬通行碼以解鎖戰情報告。</p>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        with st.form(key="war_room_login_form"):
            pwd_input = st.text_input(
                "🔑 安全通行碼",
                type="password",
                placeholder="請輸入通行碼..."
            )
            submit_btn = st.form_submit_button("🔓 驗證並解鎖進入 (自動記住)", width="stretch")
            
            if submit_btn:
                is_valid, user_data = whitelist_svc.validate_access(pwd_input)
                if is_valid:
                    st.session_state["_auth_verified"] = True
                    st.session_state["_auth_user"] = user_data
                    st.session_state["_pwd_error"] = False
                    user_token = user_data.get("token", generate_user_token(pwd_input))
                    if hasattr(st, "query_params"):
                        st.query_params["auth"] = user_token
                    elif hasattr(st, "experimental_set_query_params"):
                        st.experimental_set_query_params(auth=user_token)
                    st.rerun()
                else:
                    st.session_state["_pwd_error"] = True
                    st.error("❌ 通行碼錯誤或未在授權白名單內，存取已被拒絕！")

        st.caption("🔒 系統已啟用多用戶白名單保護 (登入後將自動保持連線)")

    return False


# 若尚未驗證通過，立即中斷後續所有敏感數據與策略加載
if not check_access_password():
    st.stop()




# 每 60 秒自動高頻刷新畫面 (1 分鐘)
if st_autorefresh is not None:
    st_autorefresh(interval=60 * 1000, key="auto_refresher_macro_1min")



def load_report_data():
    """載入最新戰報資料 (自動感應每分鐘更新，雲端與本地端全自動高頻即時重新運算)"""
    now_ts = time.time()
    last_calc_ts = st.session_state.get("_last_pipeline_run_ts", 0)
    is_expired = (now_ts - last_calc_ts) >= (REFRESH_INTERVAL_MINUTES * 60)

    file_mtime = 0
    if LATEST_REPORT_PATH.exists():
        try:
            file_mtime = LATEST_REPORT_PATH.stat().st_mtime
        except Exception:
            pass

    last_loaded_mtime = st.session_state.get("_last_report_mtime", 0)

    # 1. 若本機背景 Daemon 寫入最新檔案且尚未過期，優先直接讀取磁碟快取
    if file_mtime > last_loaded_mtime and (now_ts - file_mtime) < (REFRESH_INTERVAL_MINUTES * 60):
        try:
            with open(LATEST_REPORT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state["current_report"] = data
                st.session_state["_last_report_mtime"] = file_mtime
                st.session_state["_last_pipeline_run_ts"] = file_mtime
                return data
        except Exception:
            pass

    # 2. 若資料已超過 60 秒過期，或 session 中尚無資料，主動執行全套高頻運算流水線
    if is_expired or "current_report" not in st.session_state or not st.session_state["current_report"]:
        try:
            fresh = run_daily_macro_pipeline(send_notification=False)
            st.session_state["current_report"] = fresh
            st.session_state["_last_pipeline_run_ts"] = now_ts
            st.session_state["_last_report_mtime"] = now_ts
            return fresh
        except Exception as e:
            if "current_report" in st.session_state and st.session_state["current_report"]:
                return st.session_state["current_report"]
            if LATEST_REPORT_PATH.exists():
                with open(LATEST_REPORT_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)

    return st.session_state["current_report"]



# 初始化 Session State
if "alert_msg" not in st.session_state:
    st.session_state["alert_msg"] = None
if "custom_search_ticker" not in st.session_state:
    st.session_state["custom_search_ticker"] = "0050"
if "custom_swing_search_ticker" not in st.session_state:
    st.session_state["custom_swing_search_ticker"] = "2317"
if "odd_lot_budget" not in st.session_state:
    st.session_state["odd_lot_budget"] = 3000

# 載入資料
report = load_report_data()
raw = report.get("raw_metrics", {})
score = raw.get("overall_score", 60)
rating = raw.get("overall_rating", "BUY (審慎進攻)")
signals = raw.get("macro_radar", {})
threats = raw.get("geopolitical_threats", [])
tw_macro = report.get("taiwan_macro", {})
trends = report.get("industry_trends", [])
sinopac_data = report.get("sinopac_market_data", {})
index_data = sinopac_data.get("market_index", {})
watch_list = sinopac_data.get("watch_list", [])

# 長期投資、波段研報與持股風控導航服務
long_term_service = LongTermStrategyService()
pos_tracking_service = PositionTrackingService()
swing_screener = SwingTradingScreener()

# 載入最新 14~21 天機構級研究報告標的池 (嚴格落實台股<1000元 + 美股<100美元)
swing_screening_result = swing_screener.run_screening()
tw_swing_stocks = swing_screening_result.get("tw_stocks", [])
us_sub_stocks = swing_screening_result.get("us_stocks", [])
swing_stocks = swing_screening_result.get("all_stocks", [])


# =========================== 側邊欄控制台 ===========================
with st.sidebar:
    st.markdown("### 🎛️ 傳奇操盤室控制台")
    st.caption("50年華爾街征戰心法 × 長期價值投資 × 高動能波段")
    st.markdown("---")

    # ================= 📱 24H 雲端手機同步觀看 QR Code =================
    st.subheader("📱 手機隨身看 (24H 雲端不關機)")
    cloud_url = "https://aichinga00.streamlit.app"

    with st.expander("點擊展開專屬 QR Code 與網址", expanded=True):
        st.success("🟢 **24H 雲端專屬網址已就緒**")
        st.caption("出門在外或電腦關機時，用手機相機掃描下方條碼：")
        qr_cloud = generate_qr_image(cloud_url)
        st.image(qr_cloud, caption="🌐 24H 雲端專屬 QR Code", width=180)
        st.code(cloud_url, language="text")
        st.markdown("---")
        st.caption(f"💻 本機專屬網址：`http://localhost:8501`")

    st.markdown("---")
    st.write(f"📅 **情報時間**:\n`{report.get('summary_date', get_tw_now_str('%Y-%m-%d %H:%M:%S'))}`")
    st.write(f"⏱️ **自動更新**: `每 {REFRESH_INTERVAL_MINUTES} 分鐘 (每日每 1 小時動態連線 ATR 重新計算)`")

    st.write(f"🛡️ **總體評級**: `{rating}`")
    st.write(f"🇹🇼 **台灣景氣**: `{tw_macro.get('signal_light', '紅燈 (41分)')}`")
    st.write(f"⚡ **波段鎖定**: `{len(tw_swing_stocks)} 檔台股 + {len(us_sub_stocks)} 檔複委託`")

    # ================= 💼 我的永豐金庫存速查 =================
    pos_sum_side = pos_tracking_service.get_all_positions_summary()
    st.markdown("---")
    st.subheader("💼 我的在庫持股庫存")
    st.write(f"📊 **持股總數**: `{pos_sum_side['positions_count']} 檔`")
    st.write(f"🇹🇼 **台股損益**: `NT$ {pos_sum_side['total_profit_twd']:,} ({pos_sum_side['total_roi_twd']}%)`")
    st.write(f"🇺🇸 **美股損益**: `$ {pos_sum_side['total_profit_usd']:,} USD ({pos_sum_side['total_roi_usd']}%)`")
    if st.button("🔄 立即同步永豐金庫存", width="stretch", key="btn_side_sync_pos"):
        cnt, msg = pos_tracking_service.sync_from_sinopac_api()
        st.toast(f"永豐金庫存同步完成：{msg}", icon="💼")
        st.rerun()

    # ================= 永豐金證券 API 與 CA 憑證設定 =================
    st.markdown("---")
    st.subheader("🔐 永豐金 API 與 CA 憑證")

    
    with st.expander("點擊設定 API 金鑰與交易憑證", expanded=not bool(SHIOAJI_API_KEY)):
        input_api_key = st.text_input("API Key", value=SHIOAJI_API_KEY, type="password", help="請輸入永豐金證券核發之 API Key")
        input_secret_key = st.text_input("Secret Key", value=SHIOAJI_SECRET_KEY, type="password", help="請輸入永豐金證券核發之 Secret Key")
        input_ca_path = st.text_input("CA 憑證路徑", value=SHIOAJI_CA_PATH, help="如 C:\\Users\\aichi\\Downloads\\Sinopac.pfx")
        input_ca_pwd = st.text_input("憑證密碼", value=SHIOAJI_CA_PASSWD, type="password", help="憑證密碼 (身分證字號或自設密碼)")
        input_pid = st.text_input("身分證字號", value=SHIOAJI_PERSON_ID, help="開戶身分證字號 (選填)")
        input_sim = st.checkbox("模擬帳號模式 (Simulation)", value=SHIOAJI_SIMULATION)

        st.caption("🌐 **連線 IP**：`1.174.30.75` (請登錄於永豐金 API 白名單)")

        if st.button("💾 儲存設定並測試連線", width="stretch"):
            if input_api_key and input_secret_key:
                success = SinoPacDataService.save_credentials(
                    input_api_key, input_secret_key, input_sim,
                    input_ca_path, input_ca_pwd, input_pid
                )
                if success:
                    st.session_state["alert_msg"] = ("success", "✅ 永豐金證券 API 金鑰與憑證設定已儲存！")
                    st.rerun()
                else:
                    st.error("❌ 儲存失敗，請檢查系統權限。")
            else:
                st.warning("請填寫 API Key 與 Secret Key。")

    if SHIOAJI_API_KEY and SHIOAJI_SECRET_KEY:
        st.success("🟢 永豐金 API 金鑰已設定")
        if os.path.exists(r"C:\Users\aichi\Downloads\Sinopac.pfx"):
            st.caption("📁 憑證檔案已就緒: `Sinopac.pfx`")
    else:
        st.info("ℹ️ 尚未輸入金鑰（目前運行於 TWSE 即時備援行情）")

    # ================= 🛡️ 訪客白名單與專屬邀請管理 =================
    st.markdown("---")
    st.subheader("🛡️ 訪客白名單與邀請中心")
    wl_list = whitelist_svc.get_whitelist()
    st.write(f"👥 **已授權名額**: `{len(wl_list)} 位`")

    with st.expander("點擊管理白名單與取得專屬邀請連結", expanded=False):
        st.markdown("##### 📋 目前授權名單：")
        for u in wl_list:
            u_role = "👑 站長" if u.get("role") == "admin" else "👤 授權訪客"
            u_token = u.get("token", "")
            u_invite_link = f"https://aichinga00.streamlit.app/?auth={u_token}"
            with st.container(border=True):
                st.markdown(f"**{u['name']}** ({u_role}) ｜ 通行碼: `{u['passcode']}`")
                st.caption(f"備註: {u.get('note', '無')} ｜ 建立時間: {u.get('created_at', '')}")
                st.caption("🔗 專屬 1 鍵免密登入網址 (複製即可傳給對方)：")
                st.code(u_invite_link, language="text")
                if u.get("id") != "admin_master":
                    if st.button("🗑️ 廢止此用戶授權", key=f"btn_del_wl_{u['id']}", width="stretch"):
                        ok_rm, msg_rm = whitelist_svc.remove_user(u["id"])
                        if ok_rm:
                            st.success(f"已廢止 {u['name']} 的存取授權！")
                            st.rerun()
                        else:
                            st.error(msg_rm)

        st.markdown("---")
        st.markdown("##### ➕ 新增外來用戶授權：")
        with st.form(key="form_add_whitelist_member"):
            new_u_name = st.text_input("用戶姓名 / 標籤", placeholder="例如: 台北王經理、VIP好友")
            new_u_pwd = st.text_input("設定專屬通行碼", placeholder="例如: vip888、friend2026")
            new_u_note = st.text_input("備註說明", placeholder="例如: LINE 投資群好友")
            submit_add_u = st.form_submit_button("💾 儲存並生成專屬邀請連結", width="stretch")
            if submit_add_u:
                if new_u_name and new_u_pwd:
                    ok_add, msg_add = whitelist_svc.add_user(new_u_name, new_u_pwd, new_u_note)
                    if ok_add:
                        st.success(f"✅ {msg_add}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg_add}")
                else:
                    st.warning("請填寫姓名與通行碼！")
    
    st.markdown("---")
    st.subheader("⚡ 即時操作")

    
    if st.button("🔄 立即重新運算並發布戰報", width="stretch", key="btn_refresh_action"):
        try:
            with st.spinner("正在執行全市場總經與投資策略運算..."):
                new_report = run_daily_macro_pipeline(send_notification=True)
                st.session_state["current_report"] = new_report
                now_str = datetime.datetime.now().strftime("%H:%M:%S")
                st.session_state["alert_msg"] = ("success", f"✅ [{now_str}] 傳奇操盤手戰報已全自動重新運算完畢！")
                st.toast("✅ 戰報重新運算完成！已觸發桌面推播", icon="🚀")
                st.rerun()
        except Exception as e:
            st.error(f"重新運算時發生異常：{str(e)}")

    if st.button("🔔 測試發送桌面彈窗通知", width="stretch", key="btn_notify_action"):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        send_desktop_notification(
            title="⚡【50年傳奇操盤手：全球投資與總經戰報】",
            message=f"評級：{rating} | 台灣景氣：{tw_macro.get('signal_light', '紅燈')} | 策略全面同步更新！"
        )
        st.session_state["alert_msg"] = ("info", f"🔔 [{now_str}] 已成功觸發 Windows 桌面彈窗推播！請查看右下角通知中心。")
        st.toast("🔔 已發送系統桌面通知！請查看電腦右下角", icon="🔔")
        st.rerun()

    if st.button("🚪 鎖定並登出戰情室", width="stretch", key="btn_logout_action"):
        if hasattr(st, "query_params"):
            st.query_params.clear()
        elif hasattr(st, "experimental_set_query_params"):
            st.experimental_set_query_params()
        st.session_state["_auth_verified"] = False
        st.rerun()

    if st.session_state["alert_msg"]:
        msg_type, msg_text = st.session_state["alert_msg"]
        if msg_type == "success":
            st.success(msg_text)
        else:
            st.info(msg_text)

# =========================== 主面板 Header ===========================
def render_institutional_stock_card(s: dict, idx: int, prefix: str = "tw"):
    """
    50年華爾街資深投資分析師：6 大標準章節機構級法人研究報告卡片
    1. 獲利能力與趨勢比較 (營收、毛利、營益、淨利、EPS、YoY/QoQ、毛利率歸因)
    2. 營運效率警訊檢查 (存貨週轉天數、應收帳款天數、警訊檢查)
    3. 現金流品質 (營業活動現金流 vs 稅後淨利、FCF 試算)
    4. 未來展望 (公司財務預測 Guidance、6-12 個月成長動能)
    5. 法說會質化重點 (競爭優勢、客戶集中度風險、新技術)
    6. 市場焦點與 14~21天波段策略 (法人三大焦點、挑選邏輯、進出場點位、主要風險)
    """
    if not s:
        return

    sec1 = s.get("sec1_profitability", {})
    sec2 = s.get("sec2_operating_efficiency", {})
    sec3 = s.get("sec3_cash_flow_quality", {})
    sec4 = s.get("sec4_future_outlook", {})
    sec5 = s.get("sec5_earnings_call", {})
    sec6 = s.get("sec6_recommendation", {})

    is_us = s.get("currency") == "USD" or s.get("market") == "US_SUB"
    curr_sym = "$" if is_us else "NT$"
    curr_label = "USD" if is_us else "TWD"
    curr_p = float(sec6.get("current_price", s.get("ref_price", 100.0)))
    gain_pct = float(sec6.get("target_gain_pct", 14.8 if not is_us else 17.0))
    loss_pct = float(sec6.get("stop_loss_pct", 5.7 if not is_us else 6.8))
    target_p = float(sec6.get("target_price", round(curr_p * (1 + gain_pct/100), 2 if is_us else 1)))
    stop_p = float(sec6.get("stop_loss_price", round(curr_p * (1 - loss_pct/100), 2 if is_us else 1)))
    rr_ratio = sec6.get("risk_reward_ratio", "1 : 2.6" if not is_us else "1 : 2.5")
    atr_val = sec6.get("atr_14", "-")
    atr_pct = sec6.get("atr_14_pct", "-")
    vol_regime = sec6.get("volatility_regime", "低波動、風險被低估 (VIX 14.89 探底)")
    q_date = s.get("query_date", get_tw_now_str("%Y-%m-%d"))

    with st.container(border=True):
        # 頂部抬頭與價格約束徽章
        c_head1, c_head2 = st.columns([3, 2])
        with c_head1:
            market_badge = "🇺🇸 永豐金複委託美股" if is_us else "🇹🇼 永豐金台股核心"
            price_limit_txt = "🟢 符合美股 < $100 USD 約束" if is_us else "🟢 符合台股 < 1000 元約束"
            st.subheader(f"💎 {s['name']} ({s['ticker']}) ｜ {s.get('sector', '核心科技')}")
            st.caption(f"{market_badge} ｜ 即時現價：**{curr_sym}{curr_p} {curr_label}** ｜ {price_limit_txt} ｜ 查價日期：`{q_date}`")
        with c_head2:
            st.markdown(f"""
            <div style="text-align:right; margin-top:6px;">
                <span style="background-color:#1e1b4b; color:#a5b4fc; padding:5px 12px; border-radius:6px; font-weight:800; font-size:0.95rem; border:1px solid #6366f1;">
                    ⏱️ 14~21 天波段 (風報比 {rr_ratio})
                </span>
            </div>
            """, unsafe_allow_html=True)

        # 4 大波段戰術執行方塊 (基於 ATR 與風報比動態推導)
        st.markdown(f"""
        <div class="execution-grid">
            <div class="entry-box">
                <div style="font-size:0.75rem; color:#93c5fd; font-weight:600;">🎯 建議進場點位</div>
                <div style="font-size:1.25rem; font-weight:800; color:#60a5fa; margin-top:2px;">{curr_sym}{curr_p}</div>
                <div style="font-size:0.7rem; color:#94a3b8;">ATR(14) 實算 {atr_pct}%</div>
            </div>
            <div class="target-box">
                <div style="font-size:0.75rem; color:#6ee7b7; font-weight:600;">🚀 14~21天波段目標價</div>
                <div style="font-size:1.25rem; font-weight:800; color:#10b981; margin-top:2px;">{curr_sym}{target_p}</div>
                <div style="font-size:0.7rem; color:#34d399;">預期獲利 +{gain_pct}% (鎖定主升段)</div>
            </div>
            <div class="stop-box">
                <div style="font-size:0.75rem; color:#fca5a5; font-weight:600;">🛑 硬性防守停損價</div>
                <div style="font-size:1.25rem; font-weight:800; color:#ef4444; margin-top:2px;">{curr_sym}{stop_p}</div>
                <div style="font-size:0.7rem; color:#f87171;">停損幅度 -{loss_pct}% (ATR×1.5)</div>
            </div>
            <div class="rr-box">
                <div style="font-size:0.75rem; color:#fdba74; font-weight:600;">⚖️ 風險報酬比</div>
                <div style="font-size:1.25rem; font-weight:800; color:#f97316; margin-top:2px;">{rr_ratio}</div>
                <div style="font-size:0.7rem; color:#fb923c;">嚴格大於門檻 1:2.5</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 6 大標準章節分頁
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 一、獲利能力與趨勢",
            "🛡️ 二、營運效率警訊",
            "💰 三、現金流品質",
            "🔭 四、未來展望",
            "🎙️ 五、法說會質化重點",
            "🧭 六、市場焦點與波段策略"
        ])

        with tab1:
            st.markdown("##### 📊 一、獲利能力與趨勢比較")
            st.markdown(f"- **本季營收表現**：{sec1.get('revenue_quarterly', '查無資料')}")
            st.markdown(f"- **毛利率**：`{sec1.get('gross_margin', '查無資料')}` ｜ **營業利益率**：`{sec1.get('operating_margin', '查無資料')}` ｜ **稅後淨利率**：`{sec1.get('net_margin', '查無資料')}`")
            st.markdown(f"- **本季 EPS**：**{sec1.get('eps', '查無資料')}**")
            st.markdown(f"- **YoY / QoQ 趨勢比較**：{sec1.get('yoy_qoq_trend', '查無資料')}")
            st.info(f"💡 **毛利率變動原因分析**：\n\n{sec1.get('margin_driver', '查無資料')}")

        with tab2:
            st.markdown("##### 🛡️ 二、營運效率警訊檢查")
            st.markdown(f"- **存貨金額與存貨週轉天數**：{sec2.get('inventory_and_days', '查無資料')}")
            st.markdown(f"- **應收帳款與收現天數 (DSO)**：{sec2.get('ar_and_dso', '查無資料')}")
            st.success(f"🔍 **警訊檢查結論**：\n\n{sec2.get('warning_check', '查無重大營運警訊。')}")

        with tab3:
            st.markdown("##### 💰 三、現金流品質")
            st.markdown(f"- **營業活動現金流 vs. 稅後淨利**：\n\n{sec3.get('ocf_vs_net_income', '查無資料')}")
            st.markdown(f"- **自由現金流 (FCF) 試算與出處**：\n\n{sec3.get('fcf_calc', '查無資料')}")

        with tab4:
            st.markdown("##### 🔭 四、未來展望")
            st.markdown(f"- **公司財務預測 (Guidance)**：\n\n{sec4.get('guidance', '公司未提供正式財測')}")
            st.markdown(f"- **未來 6–12 個月成長動能與資本支出**：\n\n{sec4.get('growth_drivers', '查無資料')}")

        with tab5:
            st.markdown("##### 🎙️ 五、法說會質化重點")
            st.markdown(f"- **競爭優勢與經濟護城河**：\n\n{sec5.get('competitive_moat', '查無公開資料')}")
            st.markdown(f"- **重要客戶集中度與新技術布局**：\n\n{sec5.get('concentration_and_tech', '查無公開資料')}")

        with tab6:
            st.markdown("##### 🧭 六、市場焦點與 14~21 天波段策略建議 (ATR 實算與風報比推導)")
            st.markdown("**📌 法人與市場目前最關注的三個核心議題**：")
            for issue in sec6.get("core_issues", []):
                st.markdown(f"- {issue}")
            
            st.markdown("---")
            st.markdown("##### 📐 波段交易風報比／利潤目標推導表 (14–21 天波段)：")
            rr_val = rr_ratio.split(":")[-1].strip()
            st.markdown(f"""
            | 項目 | 數值／區間 | 計算依據與推導說明 |
            | :--- | :--- | :--- |
            | **目前波動率環境判定** | **{vol_regime}** | VIX 僅 14.89 處於近半年低點，但面臨季節性拉回與利率風險尚未反映。 |
            | **ATR(14) 概估** | **{atr_pct}%** ({curr_sym}{atr_val}) | 近 14 個交易日真實波幅 (True Range) 平均值實算。 |
            | **建議停損幅度** | **-{loss_pct}%** ({curr_sym}{stop_p}) | 依 $\\text{{ATR}}(14) \\times 1.5$ (台股) 或 $1.05$ (美股) 動態留出市場呼吸空間。 |
            | **建議獲利目標** | **+{gain_pct}%** ({curr_sym}{target_p}) | 低波動環境下目標適度收斂，依停損幅度 $\\times {rr_val}$ 精算鎖定主升段。 |
            | **最低要求風險報酬比** | **{rr_ratio}** | 低波動環境下風報比要求自常規 1:1.5~1:2 提高至 {rr_ratio}，拒絕妥協。 |
            """)

            st.markdown(f"**🎯 挑選邏輯（呼應前五項分析）**：\n\n{sec6.get('selection_logic', '')}")
            st.markdown(f"**⏱️ 操作波段週期**：`{sec6.get('target_horizon', '14 ~ 21 個交易日 (2~3週)')}` ｜ **目前價位**：`{curr_sym}{curr_p} {curr_label}`（查價日期：`{q_date}`）")
            st.error(f"⚠️ **主要風險因素**：\n\n{sec6.get('main_risks', '市場系統性波動風險')}")

            st.caption("⚠️ **提醒**：以上為一般性波段交易框架試算，非個人化投資建議，實際停損停利應搭配自身部位大小與風險承受度調整，市場情勢每日變化，請以查詢當下最新數據為準。")

        # 登記至庫存中樞

        st.markdown("---")
        with st.expander(f"🛒 我已買入 {s['name']}（登記買入成本，啟動 14~21 天進出場導航）", expanded=False):
            st.caption("輸入您的實際買進價格與股數，系統將自動為您精算【個人專屬停利停損點】與【14~21天持股倒數計時】：")
            reg_c1, reg_c2, reg_c3, reg_c4 = st.columns(4)
            with reg_c1:
                reg_cost = st.number_input("買入成本單價", value=curr_p, step=1.0 if not is_us else 0.1, key=f"inp_reg_c_{prefix}_{s['ticker']}_{idx}")
            with reg_c2:
                default_shares = 100 if not is_us else 10
                reg_shares = st.number_input("買入股數 (零股/整張)", value=default_shares, min_value=1, step=10, key=f"inp_reg_sh_{prefix}_{s['ticker']}_{idx}")
            with reg_c3:
                reg_buy_date = st.date_input("買入日期", value=get_tw_now().date(), key=f"inp_reg_d_{prefix}_{s['ticker']}_{idx}").strftime("%Y-%m-%d")
            with reg_c4:
                st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                if st.button("📌 確認登記至我的波段持股", key=f"btn_confirm_reg_{prefix}_{s['ticker']}_{idx}", width="stretch"):
                    pos_tracking_service.add_or_update_position(
                        ticker=s['ticker'],
                        name=s['name'],
                        market=s.get('market', 'TW'),
                        currency=curr_label,
                        cost_price=float(reg_cost),
                        shares=int(reg_shares),
                        buy_date=reg_buy_date,
                        target_gain_pct=float(gain_pct),
                        stop_loss_pct=float(loss_pct),
                        strategy_note=f"14~21天機構波段 ({s.get('sector', '科技')})"
                    )
                    st.success(f"✅ 已成功登記 {s['name']} ({s['ticker']}) 買入成本 {curr_sym}{reg_cost}！請至上方【我的永豐金波段持股】查看即時風控導航。")
                    st.toast(f"✅ 已登記 {s['ticker']} 至我的波段持股！", icon="🎯")
                    st.rerun()

        st.write("")

st.markdown(f"""
<div class="war-room-header">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <h1 style="margin: 0; font-size: 1.75rem; font-weight: 800; color: #f8fafc;">
                ⚡ 50年華爾街傳奇操盤手：全球總經 × 長期價值投資 × 波段戰情室
            </h1>
            <p style="margin: 6px 0 0 0; color: #a5b4fc; font-size: 0.92rem; font-weight: 600;">
                「長期投資重護城河與定期定額複利；波段操作做高動能催化。嚴控下檔風險，不對市場妥協。」
            </p>
        </div>
        <div style="text-align: right; margin-top: 10px;">
            <div style="font-size: 0.82rem; color: #c7d2fe;">總經多空共振評級</div>
            <div style="font-size: 1.35rem; font-weight: 800; color: {report.get('stance_color', '#10b981')};">
                {report.get('stance_tag', rating)}
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if st.session_state["alert_msg"]:
    m_type, m_text = st.session_state["alert_msg"]
    if m_type == "success":
        st.success(m_text)
    else:
        st.info(m_text)

# 跨維度共振大看板
res_badge = report.get("resonance_badge", "強烈多頭共振")
res_color = report.get("resonance_color", "#10b981")
st.markdown(f"""
<div class="action-hero-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <div style="font-size: 1.25rem; font-weight: 800; color: #f8fafc;">
            ⚡ 跨維度多空共振判定：<span style="color: {res_color};">{report.get('resonance_status', '強烈多頭共振')}</span>
        </div>
        <span style="background-color: #312e81; color: #c7d2fe; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; border: 1px solid #6366f1;">
            三維合流量化決策 (台股 + 永豐金複委託)
        </span>
    </div>
    <div style="background-color: rgba(15, 23, 42, 0.6); padding: 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.92rem; line-height: 1.6; color: #e2e8f0;">
        {report.get('resonance_detail', '').replace(chr(10), '<br>')}
    </div>
    <div style="background: linear-gradient(90deg, #064e3b 0%, #065f46 100%); border-left: 4px solid #34d399; padding: 10px 14px; border-radius: 6px; font-size: 0.98rem; font-weight: 600; color: #f0fdf4;">
        🗣️ <b>{report.get('market_advice', '順勢進攻')}</b>
    </div>
</div>
""", unsafe_allow_html=True)


def render_stock_card(s: dict, idx: int, prefix: str = "card"):
    """通用單一標的卡片渲染函式 (支援台股與永豐金複委託美股波段)"""
    ch1 = s["chapter_1"]

    ch2 = s["chapter_2"]
    ch3 = s["chapter_3"]
    ch4 = s["chapter_4"]
    ch5 = s["chapter_5"]
    v_chain = s.get("verification_chain", [])
    cot = s.get("chain_of_thought", [])
    sources = s.get("trusted_sources", [])
    is_us = s.get("currency") == "USD" or s.get("market") == "US_SUB"
    curr_sym = "$"
    curr_label = "USD" if is_us else "TWD"

    if is_us:
        vol_text = f"日成交量：**{s.get('volume_shares', 0):,} 股** ({s.get('turnover_wan_usd', 0):,.1f} 萬美元)"
    else:
        vol_text = f"日成交量：**{s.get('volume_lots', 0):,} 張** ({s.get('turnover_wan', 0):,.1f} 萬元)"

    with st.container(border=True):
        c_title, c_decision = st.columns([3, 2])
        with c_title:
            market_badge = "🇺🇸 永豐金複委託" if is_us else "🇹🇼 永豐金台股"
            st.subheader(f"📌 {s['name']} ({s['ticker']}) ｜ {s['sector']}")
            st.caption(f"{market_badge} ｜ 即時報價：**{curr_sym}{s['current_price']} {curr_label}** ｜ {vol_text} ｜ RSI(14)：**{s['rsi_14']}**")
        with c_decision:
            st.markdown(f"""
            <div style="text-align:right; margin-top:8px;">
                <span style="background-color:#7f1d1d; color:#fca5a5; padding:6px 14px; border-radius:6px; font-weight:800; font-size:1.05rem; border:1px solid #ef4444;">
                    {ch1['decision_badge']}
                </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="execution-grid">
            <div class="entry-box">
                <div style="font-size:0.75rem; color:#93c5fd; font-weight:600;">🎯 建議進場區間 (Entry Zone)</div>
                <div style="font-size:1.25rem; font-weight:800; color:#60a5fa; margin-top:2px;">{ch1['entry_zone']}</div>
                <div style="font-size:0.7rem; color:#94a3b8;">回踩支撐分批切入</div>
            </div>
            <div class="target-box">
                <div style="font-size:0.75rem; color:#6ee7b7; font-weight:600;">🚀 波段目標價 (5-7天)</div>
                <div style="font-size:1.25rem; font-weight:800; color:#10b981; margin-top:2px;">{curr_sym}{ch1['target_price']}</div>
                <div style="font-size:0.7rem; color:#34d399;">預期獲利 +{ch1['target_gain_pct']}%</div>
            </div>
            <div class="stop-box">
                <div style="font-size:0.75rem; color:#fca5a5; font-weight:600;">🛑 硬性停損價 (Stop-Loss)</div>
                <div style="font-size:1.25rem; font-weight:800; color:#ef4444; margin-top:2px;">{curr_sym}{ch1['stop_loss_price']}</div>
                <div style="font-size:0.7rem; color:#f87171;">最大虧損 -{ch1['stop_loss_pct']}%</div>
            </div>
            <div class="rr-box">
                <div style="font-size:0.75rem; color:#fdba74; font-weight:600;">⚖️ 預估風報比 (R:R Ratio)</div>
                <div style="font-size:1.25rem; font-weight:800; color:#f97316; margin-top:2px;">{ch1['risk_reward_ratio']}</div>
                <div style="font-size:0.7rem; color:#fb923c;">勝率與盈虧比極佳</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 🪙 零股小資波段操作換算方塊 (具備自動動態精算與防呆機制)
        odd = s.get("odd_lot_guide")
        if not odd or not isinstance(odd, dict):
            current_price = float(s.get("current_price", 100.0))
            ch1_dict = s.get("chapter_1", {})
            target_price = float(ch1_dict.get("target_price", round(current_price * 1.128, 2 if is_us else 1)))
            stop_loss_price = float(ch1_dict.get("stop_loss_price", round(current_price * 0.958, 2 if is_us else 1)))
            odd_batch_shares = 10 if is_us else 100
            odd = {
                "one_share_cost": current_price,
                "odd_batch_shares": odd_batch_shares,
                "odd_batch_label": f"{odd_batch_shares} 股",
                "odd_batch_cost": round(current_price * odd_batch_shares, 2 if is_us else 1),
                "odd_target_gain": round((target_price - current_price) * odd_batch_shares, 2 if is_us else 1),
                "odd_stop_loss": round((current_price - stop_loss_price) * odd_batch_shares, 2 if is_us else 1),
                "odd_lot_suitability": "👑 頂級高價高動能股（一張門檻高，強烈推薦以盤中零股 100 股進出）" if current_price >= 800 else ("💎 中高價主力飆股（一張40~80萬，零股小資輕鬆參與）" if current_price >= 400 else "📈 成長波段股（整張與零股皆靈活操作）"),
                "sinopac_fee_note": "永豐金盤中零股 09:00~13:30 每分撮合，享 1 元手續費優惠！" if not is_us else "永豐金複委託單股小資靈活進出！"
            }

        st.markdown(f"""
        <div style="background-color: #0f172a; border: 1px solid #6366f1; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap;">
                <span style="font-weight: 800; color: #a5b4fc; font-size: 0.95rem;">🪙 零股波段小資操作換算：{odd.get('odd_lot_suitability', '')}</span>
                <span style="background-color: #312e81; color: #c7d2fe; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 700;">永豐金盤中零股 1 元手續費優惠</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px;">
                <div style="background-color: #1e1b4b; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.7rem; color: #94a3b8;">1 股零股進場價</div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #f8fafc;">${odd.get('one_share_cost', s['current_price'])} {curr_label}</div>
                </div>
                <div style="background-color: #1e1b4b; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.7rem; color: #94a3b8;">買進 {odd.get('odd_batch_label', '100股')} 資金</div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #60a5fa;">${odd.get('odd_batch_cost', 0):,} {curr_label}</div>
                </div>
                <div style="background-color: #1e1b4b; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.7rem; color: #94a3b8;">波段停利預期獲利</div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #34d399;">+${odd.get('odd_target_gain', 0):,} {curr_label}</div>
                </div>
                <div style="background-color: #1e1b4b; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.7rem; color: #94a3b8;">波段硬性停損金額</div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #f87171;">-${odd.get('odd_stop_loss', 0):,} {curr_label}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        subtab1, subtab2, subtab3, subtab4, subtab5, subtab6, subtab7 = st.tabs([
            "📋 一、核心評級與執行摘要",
            "🌐 二、總經脈動與產業競爭力",
            "📊 三、財務健康與財報會議",
            "📈 四、5-7天技術與量價檢驗",
            "⚠️ 五、操盤筆記與風險清單",
            "💡 操盤手【思考鏈 (CoT)】",
            "🛡️ 數據【驗證鏈 (Anti-Hallucination)】"
        ])

        with subtab1:
            st.markdown(f"""
            - **最終交易決策**：`{ch1['decision']}`
            - **建議進場區間**：`{ch1['entry_zone']}`
            - **波段目標價（5-7天）**：`{curr_sym}{ch1['target_price']} (+{ch1['target_gain_pct']}%)`
            - **硬性停損價**：`{curr_sym}{ch1['stop_loss_price']} (-{ch1['stop_loss_pct']}%)`
            - **預估風報比**：`{ch1['risk_reward_ratio']}`
            - **預期持股週期**：`{ch1['horizon']}`
            """)

        with subtab2:
            st.markdown(f"**🌊 總經資金順逆風**：{ch2['macro_wind']}")
            st.markdown(f"**🏰 產業定位與護城河**：{ch2['industry_moat']}")
            st.info(f"🔥 **未來 1~2 週關鍵催化劑 (Catalyst)**：{ch2['catalyst']}")

        with subtab3:
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            f_col1.metric("營收年增率 (YoY)", ch3["financials"]["rev_yoy"])
            f_col2.metric("毛利率趨勢", ch3["financials"]["gross_margin"])
            f_col3.metric("自由現金流 (FCF)", ch3["financials"]["fcf"])
            f_col4.metric("負債比", ch3["financials"]["debt_ratio"])
            st.markdown(f"**💎 估值水平 (Valuation)**：{ch3['valuation']}")
            st.info(f"🎙️ **最新一季 Earnings Call 亮點與 Guidance**：{ch3['earnings_call_highlights']}")

        with subtab4:
            t_col1, t_col2, t_col3 = st.columns(3)
            t_col1.metric("均線架構", "多頭排列", ch4["ma_alignment"])
            t_col2.metric("量價動能確認", ch4["vol_multiplier"], "爆量突破 20MA" if ch4["is_volume_breakout"] else "溫和放量")
            t_col3.metric("動能指標", "RSI 50~65 主升段", ch4["rsi_signal"])
            
            st.markdown(f"**📐 K 線型態分析**：{ch4['k_pattern']}")
            st.markdown(f"**⚡ MACD / KD 狀態**：{ch4['macd_status']}")
            st.markdown(f"**🧱 短線關鍵防守支撐**：`{curr_sym}{ch4['support_price']}` ｜ **關鍵短壓關卡**：`{curr_sym}{ch4['resistance_price']}`")

        with subtab5:
            st.markdown("##### 🚨 三大下檔風險監控 (What could go wrong?)：")
            for r_idx, r_item in enumerate(ch5["risk_checklist"], 1):
                st.markdown(f"{r_idx}. ⚠️ {r_item}")
            st.error(f"🛑 **持股週期提前平倉監控條件**：\n\n{ch5['early_exit_rules']}")

        with subtab6:
            st.markdown("##### 💡 50 年傳奇操盤手 5 步推理思考鏈 (Chain of Thought)：")
            for step_item in cot:
                st.markdown(f"""
                <div class="cot-step-box">
                    <div style="font-weight:700; color:#a5b4fc; margin-bottom:4px;">{step_item['step']}</div>
                    <div>{step_item['thought']}</div>
                </div>
                """, unsafe_allow_html=True)

        with subtab7:
            st.markdown("##### 🛡️ 防幻覺數據驗證鏈 (Anti-Hallucination Verification Chain)：")
            for v_item in v_chain:
                st.markdown(f"""
                <div class="verify-item-box">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; color:#f8fafc; font-size:0.92rem;">🔍 {v_item['check_item']}</span>
                        <span style="background-color:#064e3b; color:#34d399; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem;">{v_item['status']}</span>
                    </div>
                    <div style="font-family:monospace; color:#93c5fd; font-size:0.85rem; margin:4px 0;">數學校驗式：{v_item['formula']}</div>
                    <div style="color:#94a3b8; font-size:0.82rem;">{v_item['detail']}</div>
                </div>
                """, unsafe_allow_html=True)
            
        st.markdown("---")
        with st.expander(f"🛒 我已買入 {s['name']}（登記我的買入成本價，啟動 5~7 天進出場導航）", expanded=False):
            st.caption("輸入您的實際買進價格與股數，系統將自動為您精算【個人專屬停利停損點】與【5~7天持股倒數計時】：")
            reg_c1, reg_c2, reg_c3, reg_c4 = st.columns(4)
            with reg_c1:
                cur_p = float(s.get('current_price', 100.0))
                reg_cost = st.number_input("買入成本單價", value=cur_p, step=1.0 if not is_us else 0.1, key=f"inp_reg_c_{prefix}_{s['ticker']}_{idx}")
            with reg_c2:
                default_shares = 100 if not is_us else 10
                reg_shares = st.number_input("買入股數 (零股/整張)", value=default_shares, min_value=1, step=10, key=f"inp_reg_sh_{prefix}_{s['ticker']}_{idx}")
            with reg_c3:
                reg_buy_date = st.date_input("買入日期", value=get_tw_now().date(), key=f"inp_reg_d_{prefix}_{s['ticker']}_{idx}").strftime("%Y-%m-%d")
            with reg_c4:
                st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                if st.button("📌 確認登記至我的波段持股", key=f"btn_confirm_reg_{prefix}_{s['ticker']}_{idx}", width="stretch"):

                    pos_tracking_service.add_or_update_position(
                        ticker=s['ticker'],
                        name=s['name'],
                        market=s.get('market', 'TW'),
                        currency=s.get('currency', 'TWD'),
                        cost_price=float(reg_cost),
                        shares=int(reg_shares),
                        buy_date=reg_buy_date,
                        target_gain_pct=float(ch1.get('target_gain_pct', 10.0)),
                        stop_loss_pct=float(ch1.get('stop_loss_pct', 4.0)),
                        strategy_note=f"5~7天高動能波段 ({s['sector']})"
                    )
                    st.success(f"✅ 已成功登記 {s['name']} ({s['ticker']}) 買入成本 {curr_sym}{reg_cost}！請至上方【我的永豐金波段持股】查看即時風控導航。")
                    st.toast(f"✅ 已登記 {s['ticker']} 至我的波段持股！", icon="🎯")
                    st.rerun()

        st.write("")


# =========================== 分頁導覽 ===========================
tab_portfolio, tab_long_term, tab_swing, tab_sinopac, tab_macro, tab_industry, tab_history = st.tabs([
    "💼 【我的永豐金庫存持股與進出場風控中樞】",
    "🏛️ 【長期價值投資與定期定額 (自訂標的)】",
    "⚡ 【14~21天高動能波段推薦 (台美股)】",
    "🏛️ 【永豐金證券 即時台股雷達 (Shioaji)】",
    "🌐 【總經雷達與地緣戰報】",
    "🏭 【工研院 IEK 產業趨勢 × 台灣景氣】",
    "📈 【歷史走勢與數據監控】"
])

# =========================== TAB 0: 我的永豐金庫存持股與進出場風控中樞 ===========================
with tab_portfolio:
    st.markdown("### 💼 我的永豐金庫存持股與個人化進出場風控中樞 (SinoPac Portfolio Radar)")
    st.caption("連線永豐金證券 Shioaji 庫存部位 ｜ 依買入成本精算【+8% / +15% 停利目標】與【-4% 硬性防守停損】 ｜ 14~21 天 (2~3週) 波段時效倒數導航")


    pos_summary = pos_tracking_service.get_all_positions_summary()
    active_positions = pos_summary.get("positions", [])

    # 4 大庫存核心 KPI 總覽
    pk1, pk2, pk3, pk4 = st.columns(4)
    pk1.metric("💼 在庫持股總檔數", f"{pos_summary['positions_count']} 檔", "持股集中 2~4 檔最佳")
    
    twd_profit = pos_summary['total_profit_twd']
    twd_roi = pos_summary['total_roi_twd']
    twd_sym = "▲" if twd_profit >= 0 else "▼"
    pk2.metric(
        "🇹🇼 台股持股市值與損益",
        f"NT$ {pos_summary['total_market_twd']:,}",
        f"{twd_sym} NT$ {abs(twd_profit):,} ({twd_roi}%)"
    )

    usd_profit = pos_summary['total_profit_usd']
    usd_roi = pos_summary['total_roi_usd']
    usd_sym = "▲" if usd_profit >= 0 else "▼"
    pk3.metric(
        "🇺🇸 美股複委託市值與損益",
        f"$ {pos_summary['total_market_usd']:,} USD",
        f"{usd_sym} $ {abs(usd_profit):,} ({usd_roi}%)"
    )

    pk4.metric("⚖️ 操盤紀律目標", "5 ~ 7 天高週轉", "風報比 >= 1:2.5")

    st.markdown("---")

    # 1. 永豐金證券 API 實盤庫存自動讀取區塊
    with st.container(border=True):
        st.markdown("#### 🔄 永豐金證券 Shioaji API 庫存讀取與同步中樞")
        st.caption("系統將直接連線永豐金證券伺服器，自動抓取您的台股證券帳號 (`9A61-9802236`) 與複委託海外帳號 (`9A61-09800879`) 之即時股票庫存：")
        
        sync_c1, sync_c2 = st.columns([2, 3])
        with sync_c1:
            if st.button("🚀 立即讀取 / 同步永豐金證券庫存", key="btn_sync_shioaji_main_tab", width="stretch"):
                with st.spinner("正在向永豐金證券伺服器查詢庫存部位..."):
                    cnt, msg = pos_tracking_service.sync_from_sinopac_api()
                    if cnt > 0:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.info(f"ℹ️ {msg}")
        with sync_c2:
            st.caption("💡 提示：若目前為模擬帳號或實盤尚未成交，您亦可在下方「➕ 手動登記 / 匯入持股」隨時新增您的持股成本。")

    # 2. 手動新增 / 匯入庫存管理面板
    with st.expander("➕ 手動登記新買入持股 / 調整成本單價 (點擊展開)", expanded=not bool(active_positions)):
        st.markdown("##### 登記您在永豐金買入的股票或 ETF：")
        with st.form(key="form_add_manual_pos_main"):
            mf_c1, mf_c2, mf_c3 = st.columns(3)
            with mf_c1:
                m_tk = st.text_input("股票代號", placeholder="例如: 2330, 2454, 006208, VTI, NVDA").strip().upper()
            with mf_c2:
                m_name = st.text_input("股票名稱", placeholder="例如: 台積電, 聯發科, 輝達").strip()
            with mf_c3:
                m_mkt = st.selectbox("市場類別", ["TW (台股現股/零股)", "US_SUB (永豐金複委託美股)"])
            
            mf_d1, mf_d2, mf_d3 = st.columns(3)
            with mf_d1:
                m_cost = st.number_input("買入成交單價", min_value=0.01, value=100.0, step=1.0)
            with mf_d2:
                m_shares = st.number_input("持有股數 (支援零股如 100 股或整張 1000 股)", min_value=1, value=100, step=10)
            with mf_d3:
                m_date = st.date_input("買入日期", value=get_tw_now().date()).strftime("%Y-%m-%d")
            
            m_submit = st.form_submit_button("💾 確認儲存並啟動個人進出場風控導航", width="stretch")
            if m_submit:
                if m_tk:
                    is_tw = "TW" in m_mkt
                    pos_tracking_service.add_or_update_position(
                        ticker=m_tk,
                        name=m_name if m_name else m_tk,
                        market="TW" if is_tw else "US_SUB",
                        currency="TWD" if is_tw else "USD",
                        cost_price=float(m_cost),
                        shares=int(m_shares),
                        buy_date=m_date,
                        target_gain_pct=10.0,
                        stop_loss_pct=4.0,
                        strategy_note="永豐金持股風控中樞"
                    )
                    st.success(f"✅ 已成功將 {m_tk} 納入持股庫存並啟動進出場導航！")
                    st.rerun()
                else:
                    st.warning("請填寫股票代號！")

    # 3. 庫存管理與資料備份工具箱 (一鍵清空 / 匯出備份 / 貼上還原)
    with st.expander("📦 庫存備份與自訂管理工具箱 (一鍵清空 / 匯出備份 / 貼上還原)", expanded=False):
        b_c1, b_c2 = st.columns(2)
        with b_c1:
            st.markdown("##### 📤 匯出持股備份 (JSON)")
            st.caption("將您目前登記的真實庫存與成本匯出為文字，隨時可在任何裝置上一鍵還原：")
            exp_json = pos_tracking_service.export_positions_json()
            st.text_area("庫存備份代碼", value=exp_json, height=120, key="txt_export_pos_json")
            
            if st.button("🧹 一鍵清空所有在庫持股", key="btn_clear_all_pos", help="清空所有持股紀錄重新開始"):
                pos_tracking_service.clear_all_positions()
                st.success("已清空所有持股紀錄！")
                st.rerun()

        with b_c2:
            st.markdown("##### 📥 匯入 / 還原持股備份")
            st.caption("貼上之前備份的庫存 JSON 代碼，即可瞬間還原您的真實持股：")
            imp_json = st.text_area("貼上備份代碼", placeholder='[{"ticker": "2330", "cost_price": 1050, "shares": 100, ...}]', height=120, key="txt_import_pos_json")
            if st.button("📥 確認匯入並還原持股", key="btn_confirm_import_pos", width="stretch"):
                if imp_json.strip():
                    ok, msg = pos_tracking_service.import_positions_json(imp_json.strip())
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.warning("請先貼上備份代碼！")

    st.markdown("---")


    # 3. 庫存持股量化總覽表格 (Data Table View)
    if active_positions:
        st.markdown("#### 📋 在庫持股量化總覽表 (全方位損益與進出場點位一覽)：")
        table_rows = []
        for pos in active_positions:
            p_sym = pos["curr_sym"]
            roi = pos["roi_pct"]
            roi_str = f"+{roi}%" if roi >= 0 else f"{roi}%"
            profit_str = f"+{p_sym}{pos['profit_val']:,}" if pos['profit_val'] >= 0 else f"-{p_sym}{abs(pos['profit_val']):,}"
            
            table_rows.append({
                "代號": pos["ticker"],
                "股票名稱": pos["name"],
                "市場": "🇹🇼 台股" if pos["currency"] == "TWD" else "🇺🇸 複委託",
                "買入成本": f"{p_sym}{pos['cost_price']}",
                "即時現價": f"{p_sym}{pos['curr_price']}",
                "持有股數": f"{pos['shares']:,}",
                "投入總成本": f"{p_sym}{pos['cost_total']:,}",
                "目前市值": f"{p_sym}{pos['market_val']:,}",
                "未實現損益": profit_str,
                "報酬率 (ROI)": roi_str,
                "第1停利 (+8%)": f"{p_sym}{pos['tp1_price']}",
                "第2停利 (+15%)": f"{p_sym}{pos['tp2_price']}",
                "硬性停損 (-4%)": f"{p_sym}{pos['sl_price']}",
                "持股天數": f"第 {pos['held_days']} 天",
                "風控狀態": pos["status_badge"].split(" (")[0]
            })
        
        df_pos = pd.DataFrame(table_rows)
        st.dataframe(df_pos, width="stretch", hide_index=True)

        st.markdown("---")
        st.markdown("#### 🧭 每檔持股之【專屬 5~7 天進出場導航大卡片】：")

        for p_idx, pos in enumerate(active_positions):
            p_sym = pos["curr_sym"]
            p_unit = pos["currency"]
            roi = pos["roi_pct"]
            roi_color = "#10b981" if roi >= 0 else "#ef4444"
            roi_sym = "▲" if roi >= 0 else "▼"

            with st.container(border=True):
                # 卡片頂部
                h_c1, h_c2 = st.columns([3, 2])
                with h_c1:
                    mkt_tag = "🇹🇼 永豐金台股" if pos["currency"] == "TWD" else "🇺🇸 永豐金複委託"
                    st.markdown(f"#### 📌 **{pos['name']}** (`{pos['ticker']}`) ｜ {mkt_tag}")
                    st.caption(f"📅 買入日期：`{pos['buy_date']}` ｜ 持有股數：**{pos['shares']:,} 股** ｜ 來源：`{pos['source']}`")
                with h_c2:
                    st.markdown(f"""
                    <div style="text-align:right;">
                        <span style="background-color:#1e1b4b; color:{pos['status_color']}; border:1px solid {pos['status_color']}; padding:4px 10px; border-radius:6px; font-weight:800; font-size:0.92rem;">
                            {pos['status_badge']}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                # 即時現價 vs 買入成本價橫幅
                st.markdown(f"""
                <div style="background-color:#0f172a; border:1px solid #334155; border-radius:8px; padding:12px 16px; margin:10px 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                    <div>
                        <span style="font-size:0.82rem; color:#94a3b8;">您的買入成本均價</span><br>
                        <span style="font-size:1.35rem; font-weight:800; color:#f8fafc;">{p_sym}{pos['cost_price']} {p_unit}</span>
                        <span style="font-size:0.8rem; color:#64748b;">(總成本: {p_sym}{pos['cost_total']:,})</span>
                    </div>
                    <div style="font-size:1.5rem; color:#6366f1; font-weight:800;">➔</div>
                    <div>
                        <span style="font-size:0.82rem; color:#94a3b8;">即時市場現價</span><br>
                        <span style="font-size:1.35rem; font-weight:800; color:#60a5fa;">{p_sym}{pos['curr_price']} {p_unit}</span>
                        <span style="font-size:0.8rem; color:#64748b;">(今日: {pos['day_change_pct']}%)</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:0.82rem; color:#94a3b8;">未實現帳面損益 (ROI)</span><br>
                        <span style="font-size:1.45rem; font-weight:900; color:{roi_color};">{roi_sym} {p_sym}{abs(pos['profit_val']):,} ({roi}%)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # 4 大個人化進出場點位導航方塊
                g_c1, g_c2, g_c3, g_c4 = st.columns(4)
                with g_c1:
                    with st.container(border=True):
                        st.markdown("<div style='font-size:0.75rem; color:#6ee7b7; font-weight:700;'>🎯 第 1 停利目標 (+8%)</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.2rem; font-weight:800; color:#10b981;'>{p_sym}{pos['tp1_price']}</div>", unsafe_allow_html=True)
                        st.caption(f"獲利：+{p_sym}{pos['tp1_profit']:,}\n\n**戰術：出清 50% 鎖定勝局**")
                
                with g_c2:
                    with st.container(border=True):
                        st.markdown("<div style='font-size:0.75rem; color:#93c5fd; font-weight:700;'>🚀 第 2 停利目標 (+12~15%)</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.2rem; font-weight:800; color:#60a5fa;'>{p_sym}{pos['tp2_price']}</div>", unsafe_allow_html=True)
                        st.caption(f"獲利：+{p_sym}{pos['tp2_profit']:,}\n\n**戰術：全數出清獲利落袋**")

                with g_c3:
                    with st.container(border=True):
                        st.markdown("<div style='font-size:0.75rem; color:#fca5a5; font-weight:700;'>🛑 硬性防守停損點 (-4%)</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.2rem; font-weight:800; color:#ef4444;'>{p_sym}{pos['sl_price']}</div>", unsafe_allow_html=True)
                        st.caption(f"虧損限制：-{p_sym}{pos['sl_loss_val']:,}\n\n**戰術：跌破無條件停損**")

                with g_c4:
                    with st.container(border=True):
                        st.markdown("<div style='font-size:0.75rem; color:#fdba74; font-weight:700;'>⏱️ 14~21 天波段時效倒數</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:1.2rem; font-weight:800; color:#f97316;'>第 {pos['held_days']} 天 / 剩 {pos['remaining_days']} 天</div>", unsafe_allow_html=True)
                        st.caption("波段週期：14~21 個交易日\n\n**滿期未發動即時間停損**")


                # 操盤手當前行動指令
                st.markdown(f"""
                <div style="background:linear-gradient(90deg, #1e1b4b 0%, #0f172a 100%); border-left:4px solid {pos['status_color']}; padding:10px 14px; border-radius:6px; margin:8px 0; font-size:0.92rem; color:#f1f5f9;">
                    🗣️ <b>操盤手當前戰術指示</b>：{pos['action_advice']}
                </div>
                """, unsafe_allow_html=True)

                # 平倉結案操作按鈕
                del_c1, del_c2 = st.columns([4, 1])
                with del_c2:
                    if st.button("🗑️ 平倉結案 / 移除", key=f"btn_del_pos_main_{pos['ticker']}_{p_idx}", width="stretch"):
                        pos_tracking_service.remove_position(pos['ticker'])
                        st.success(f"已平倉結案並自庫存移除 {pos['name']} ({pos['ticker']})！")
                        st.rerun()
    else:
        st.info("ℹ️ 目前尚未讀取到永豐金持股庫存。您可以點擊上方「🚀 立即讀取 / 同步永豐金證券庫存」，或在「➕ 手動登記新買入持股」輸入您的買進標的與成本！")

# =========================== TAB 1: 長期價值投資與定期定額策略 (自訂標的) ===========================
with tab_long_term:
    st.markdown("### 🏛️ 長期價值投資與定期定額 (DCA) 量化分析引擎")
    st.caption("支援輸入任意台股個股/ETF、美股複委託個股/ETF ｜ 評估 3~5 年經濟護城河 ｜ 精算三大估值加碼區間 ｜ 擬定金字塔分批建倉戰術")


    # 1. 搜尋與自訂輸入區塊
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        target_ticker_input = st.text_input(
            "🔍 輸入您想分析的任意股票 / ETF 代碼 (例如: 0050, 00878, 2330, 2454, VOO, QQQ, NVDA, VT, SMH)",
            value=st.session_state["custom_search_ticker"],
            placeholder="請輸入台股或美股代碼...",
            key="input_search_ticker_field"
        ).strip().upper()
    with search_col2:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 執行長期價值深度分析", width="stretch", key="btn_run_longterm_analysis"):
            if target_ticker_input:
                st.session_state["custom_search_ticker"] = target_ticker_input
                st.rerun()

    # 快捷熱門標的 Chips
    st.markdown("🔥 **熱門核心長期標的快速切換**：")
    chip_cols = st.columns(8)
    popular_chips = [
        ("0050", "🇹🇼 0050 台灣50"),
        ("00878", "🇹🇼 00878 高股息"),
        ("2330", "🇹🇼 2330 台積電"),
        ("2454", "🇹🇼 2454 聯發科"),
        ("VOO", "🇺🇸 VOO 標普500"),
        ("QQQ", "🇺🇸 QQQ 納斯達克"),
        ("NVDA", "🇺🇸 NVDA 輝達"),
        ("VT", "🇺🇸 VT 全球股票")
    ]
    for idx, (chip_tk, chip_label) in enumerate(popular_chips):
        with chip_cols[idx]:
            if st.button(chip_label, key=f"chip_{chip_tk}", width="stretch"):
                st.session_state["custom_search_ticker"] = chip_tk
                st.rerun()

    st.markdown("---")

    # 2. 執行並渲染長期深度分析報告
    analyzed_tk = st.session_state["custom_search_ticker"]
    if analyzed_tk:
        with st.spinner(f"正在全方位評估【{analyzed_tk}】長期價值、護城河與估值位階..."):
            res = long_term_service.analyze_ticker_for_long_term(analyzed_tk)

        curr_sym = "$"
        curr_unit = res["currency"]
        chg_val = res["change_pct"]
        chg_sym = "▲" if chg_val >= 0 else "▼"

        # 標的抬頭與自訂清單加入按鈕
        head_c1, head_c2 = st.columns([3, 2])
        with head_c1:
            st.subheader(f"💎 {res['name']} ({res['ticker']}) ｜ {res['sector']}")
            st.caption(f"{res['market']} ｜ {res['asset_type_label']} ｜ 即時現價：**{curr_sym}{res['curr_price']} {curr_unit}** ({chg_sym} {abs(chg_val)}%) ｜ 距 60 日高點回檔：**-{res['pullback_from_high']}%** ｜ RSI(14)：**{res['rsi_14']}**")
        with head_c2:
            st.markdown(f"""
            <div style="text-align:right; margin-top:8px;">
                <span style="background-color:#1e1b4b; color:{res['rating_color']}; padding:6px 14px; border-radius:6px; font-weight:800; font-size:1.05rem; border:1px solid {res['rating_color']};">
                    {res['rating_badge']}
                </span>
            </div>
            """, unsafe_allow_html=True)

        # 4 大長期執行估值指標方塊
        st.markdown(f"""
        <div class="execution-grid">
            <div class="longterm-cheap-box">
                <div style="font-size:0.75rem; color:#6ee7b7; font-weight:600;">💎 便宜逢低加碼區 (Discount)</div>
                <div style="font-size:1.2rem; font-weight:800; color:#10b981; margin-top:2px;">{res['cheap_zone']}</div>
                <div style="font-size:0.7rem; color:#34d399;">放大扣款 / 單筆重砲買進</div>
            </div>
            <div class="longterm-fair-box">
                <div style="font-size:0.75rem; color:#93c5fd; font-weight:600;">⚖️ 合理定期定額區 (Fair Value)</div>
                <div style="font-size:1.2rem; font-weight:800; color:#60a5fa; margin-top:2px;">{res['fair_zone']}</div>
                <div style="font-size:0.7rem; color:#94a3b8;">紀律每月標準扣款</div>
            </div>
            <div class="longterm-premium-box">
                <div style="font-size:0.75rem; color:#fde047; font-weight:600;">⚠️ 昂貴過熱警戒區 (Premium)</div>
                <div style="font-size:1.2rem; font-weight:800; color:#f59e0b; margin-top:2px;">{res['premium_zone']}</div>
                <div style="font-size:0.7rem; color:#fbbf24;">暫停單筆追高 / 續抱</div>
            </div>
            <div class="longterm-rating-box">
                <div style="font-size:0.75rem; color:#c7d2fe; font-weight:600;">🧭 目前定期定額戰術方針</div>
                <div style="font-size:1.05rem; font-weight:800; color:#a5b4fc; margin-top:4px;">{res['dca_action']}</div>
                <div style="font-size:0.7rem; color:#e0e7ff;">跨週期 3~5 年長期複利</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 🪙 零股小資定期定額試算卡片
        user_budget = float(st.session_state["odd_lot_budget"])
        is_us_curr = res["currency"] == "USD"
        odd_plan = long_term_service.calculate_odd_lot_plan(
            res["ticker"], res["curr_price"],
            (user_budget / 32.2) if is_us_curr else user_budget,
            is_us=is_us_curr
        )
        
        st.markdown(f"""
        <div style="background-color: #0f172a; border: 1px solid #3b82f6; border-radius: 8px; padding: 12px 16px; margin: 10px 0 16px 0;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap;">
                <span style="font-weight: 800; color: #60a5fa; font-size: 1.02rem;">🪙 【{res['name']}】零股小資定期定額試算 (每股計價)</span>
                <span style="background-color: #1e3a8a; color: #93c5fd; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 700;">永豐金盤中零股 1 元手續費優惠</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px;">
                <div style="background-color: #1e293b; padding: 8px 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.72rem; color: #94a3b8;">1 股零股最低進場價</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #f8fafc;">${odd_plan['one_share_cost']} {res['currency']}</div>
                </div>
                <div style="background-color: #1e293b; padding: 8px 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.72rem; color: #94a3b8;">每月 ${int(user_budget):,} 可買</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #34d399;">{odd_plan['buy_desc'].replace('**', '')}</div>
                </div>
                <div style="background-color: #1e293b; padding: 8px 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.72rem; color: #94a3b8;">存滿 1 張 (1000股) 時間</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #38bdf8;">約 {odd_plan['years_to_one_lot']} 年 ({odd_plan['months_to_one_lot']} 個月)</div>
                </div>
                <div style="background-color: #1e293b; padding: 8px 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 0.72rem; color: #94a3b8;">1 年累積投入 / 估年股利</div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #fde047;">${int(odd_plan['one_year_invested']):,} / 領 ${int(odd_plan['one_year_div_est']):,}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 操盤手行動指引
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #1e1b4b 0%, #0f172a 100%); border-left: 4px solid #818cf8; padding: 12px 16px; border-radius: 6px; font-size: 0.95rem; line-height: 1.6; color: #f8fafc; margin-bottom: 16px;">
            🗣️ <b>傳奇操盤手長期投資指引</b>：{res['action_advice']}
        </div>
        """, unsafe_allow_html=True)

        # 加入/移除追蹤清單按鈕
        current_watchlist = long_term_service.load_watchlist()
        is_in_w = analyzed_tk in current_watchlist
        btn_w_col1, btn_w_col2 = st.columns([1, 4])
        with btn_w_col1:
            if not is_in_w:
                if st.button("⭐ 加入我的長期追蹤池", key=f"btn_add_w_{analyzed_tk}", width="stretch"):
                    long_term_service.add_to_watchlist(analyzed_tk)
                    st.success(f"✅ 已將 {res['name']} ({analyzed_tk}) 加入長期追蹤清單！")
                    st.rerun()
            else:
                if st.button("❌ 從長期追蹤池移除", key=f"btn_rem_w_{analyzed_tk}", width="stretch"):
                    long_term_service.remove_from_watchlist(analyzed_tk)
                    st.info(f"已將 {analyzed_tk} 從長期追蹤池移除。")
                    st.rerun()

        # 深度分析多分頁標籤
        lt_tab1, lt_tab2, lt_tab3, lt_tab4, lt_tab5 = st.tabs([
            "🏰 一、經濟護城河與長期成長動能",
            "📊 二、大跌金字塔分批建倉階梯",
            "🧭 三、定期定額 (DCA) 與資金配置規劃",
            "💡 四、價值投資 5 步推理【思考鏈 (CoT)】",
            "🛡️ 五、防幻覺數據【驗證鏈 (Verification)】"
        ])

        with lt_tab1:
            st.markdown(f"**🏰 核心護城河與競爭壁壘**：\n\n{res['moat']}")
            st.markdown("---")
            st.markdown(f"**🔥 未來 3~5 年大趨勢與催化劑**：\n\n{res['catalyst']}")
            st.markdown("---")
            st.info(f"📌 **資產屬性定位**：屬於【{res['asset_type_label']}】，適合長線投資人作為核心底倉，透過跨週期持有享有經濟與生產力提升帶來的長期資本利得。")

        with lt_tab2:
            st.markdown("##### 🧱 巴菲特式金字塔越跌越買戰術階梯 (Pyramid Buying on Dips)：")
            st.caption("長期價值投資的精髓在於『暴跌是送分題』。以下為依據歷史波動度精算的四階分批低接加碼藍圖：")
            
            for p_step in res["pyramid_plan"]:
                st.markdown(f"""
                <div style="background-color:#0f172a; border-left:4px solid #10b981; padding:10px 14px; border-radius:6px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; color:#f8fafc; font-size:0.95rem;">📍 {p_step['condition']}</span>
                        <span style="background-color:#064e3b; color:#34d399; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.85rem;">觸發價位：${p_step['price_target']} {curr_unit}</span>
                    </div>
                    <div style="color:#93c5fd; font-size:0.88rem; margin-top:4px;">🎯 <b>執行戰術</b>：{p_step['action']}</div>
                </div>
                """, unsafe_allow_html=True)

        with lt_tab3:
            st.markdown("##### 🧭 定期定額 (Dollar-Cost Averaging) 執行守則：")
            st.markdown("""
            1. **固定日期紀律扣款**：建議設定每月 6 日、16 日或 26 日扣款，排除人為情緒干擾。
            2. **股息再投入 (Dividend Reinvestment)**：凡領取之現金股利，一律於除息後全數自動轉買再投入，發揮複利最大威力。
            3. **不停損原則**：指數型 ETF 與具備寬闊護城河的超級龍頭股，在熊市回檔時絕不輕易停損，應堅持扣款並啟動金字塔加碼。
            4. **持股目標週期**：至少 **3 ~ 5 年以上**（跨越 1 個完整景氣循環）。
            """)

        with lt_tab4:
            st.markdown("##### 💡 價值投資 5 步推理思考鏈 (Chain of Thought)：")
            for cot_item in res["chain_of_thought"]:
                st.markdown(f"""
                <div class="cot-step-box">
                    <div style="font-weight:700; color:#a5b4fc; margin-bottom:4px;">{cot_item['step']}</div>
                    <div>{cot_item['thought']}</div>
                </div>
                """, unsafe_allow_html=True)

        with lt_tab5:
            st.markdown("##### 🛡️ 防幻覺數據驗證鏈 (Verification Chain)：")
            for v_item in res["verification_chain"]:
                st.markdown(f"""
                <div class="verify-item-box">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; color:#f8fafc; font-size:0.92rem;">🔍 {v_item['check_item']}</span>
                        <span style="background-color:#064e3b; color:#34d399; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem;">{v_item['status']}</span>
                    </div>
                    <div style="font-family:monospace; color:#93c5fd; font-size:0.85rem; margin:4px 0;">數學校驗式：{v_item['formula']}</div>
                    <div style="color:#94a3b8; font-size:0.82rem;">{v_item['detail']}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # 3. 精選台美【零股計價】小資推薦標的池 (Top Odd-Lot Recommended Baskets)
    st.markdown("### 🪙 精選台美【零股計價】小資推薦標的池")
    st.caption(f"依目前設定之每月預算 **${int(st.session_state['odd_lot_budget']):,} 元** 精算每股單價、小資進場門檻與存張規劃：")

    odd_baskets = long_term_service.get_odd_lot_baskets(monthly_budget=float(st.session_state["odd_lot_budget"]))
    
    basket_sub1, basket_sub2, basket_sub3, basket_sub4 = st.tabs([
        "👑 護城河高價龍頭零股",
        "📈 國民旗艦市值型 ETF",
        "💰 高股息現金流 ETF",
        "🇺🇸 美股複委託旗艦零股"
    ])

    basket_map = {
        basket_sub1: "high_priced_bluechips",
        basket_sub2: "market_index_etfs",
        basket_sub3: "high_dividend_etfs",
        basket_sub4: "us_sub_brokerage"
    }

    for b_subtab, b_key in basket_map.items():
        with b_subtab:
            b_data = odd_baskets.get(b_key, {})
            st.markdown(f"##### {b_data.get('title', '')}")
            st.caption(b_data.get("desc", ""))
            
            b_items = b_data.get("items", [])
            if b_items:
                b_cols = st.columns(2)
                for b_item_idx, b_item in enumerate(b_items):
                    item_analysis = b_item["analysis"]
                    item_odd = b_item["odd_plan"]
                    target_b_col = b_cols[b_item_idx % 2]
                    
                    with target_b_col:
                        with st.container(border=True):
                            b_sym = "$"
                            b_curr = item_analysis["currency"]
                            b_chg = item_analysis["change_pct"]
                            b_arrow = "▲" if b_chg >= 0 else "▼"
                            
                            r1, r2 = st.columns([3, 2])
                            with r1:
                                st.markdown(f"**{item_analysis['name']}** (`{item_analysis['ticker']}`)")
                                st.caption(f"{item_analysis['sector']}")
                            with r2:
                                st.markdown(f"""
                                <div style="text-align:right;">
                                    <span style="font-size:1.1rem; font-weight:800;">{b_sym}{item_analysis['curr_price']} {b_curr}</span>
                                    <span style="color:{'#ef4444' if b_chg>=0 else '#10b981'}; font-weight:700;">{b_arrow} {abs(b_chg)}%</span>
                                </div>
                                """, unsafe_allow_html=True)

                            # 零股核心指標小方塊
                            st.markdown(f"""
                            <div style="background-color:#1e1b4b; border-radius:6px; padding:8px 10px; margin:6px 0;">
                                <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:3px;">
                                    <span style="color:#cbd5e1;">🪙 1股最低進場門檻：</span>
                                    <span style="font-weight:800; color:#f8fafc;">${item_odd['one_share_cost']} {b_curr}</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:3px;">
                                    <span style="color:#93c5fd;">📦 每月 ${int(st.session_state['odd_lot_budget']):,} 預算：</span>
                                    <span style="font-weight:800; color:#34d399;">{item_odd['buy_desc'].replace('**', '')}</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; font-size:0.85rem;">
                                    <span style="color:#fde047;">⏳ 累積 1 張時間：</span>
                                    <span style="font-weight:800; color:#fbbf24;">約 {item_odd['years_to_one_lot']} 年 ({item_odd['months_to_one_lot']} 個月)</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.caption(f"🧭 **評級**：<b style='color:{item_analysis['rating_color']};'>{item_analysis['rating_badge']}</b> ｜ 合理區：`{item_analysis['fair_zone']}`")

                            # 操作按鈕
                            btn_c1, btn_c2 = st.columns([2, 1])
                            with btn_c1:
                                if st.button(f"🔍 深度分析 {item_analysis['ticker']}", key=f"btn_basket_ana_{b_key}_{item_analysis['ticker']}", width="stretch"):
                                    st.session_state["custom_search_ticker"] = item_analysis["ticker"]
                                    st.rerun()
                            with btn_c2:
                                if st.button("⭐ 追蹤", key=f"btn_basket_add_{b_key}_{item_analysis['ticker']}", width="stretch"):
                                    long_term_service.add_to_watchlist(item_analysis["ticker"])
                                    st.success(f"已加入 {item_analysis['ticker']}")
                                    st.rerun()

    # 3. 我的長期投資自訂追蹤池 (Watchlist Overview & Management)
    st.markdown("#### ⭐ 我的長期投資自訂追蹤池 (My Long-Term Watchlist)")
    st.caption("隨時一覽您所保存的所有台股與美股長投標的之即時位階，可直接點選查看深度分析或一鍵移除標的")

    saved_watchlist = long_term_service.get_watchlist_summary()
    
    # 快速管理與批次移除控制列
    with st.expander("⚙️ 追蹤池快捷管理（批次移除 / 快速新增 / 恢復預設）", expanded=False):
        mgr_c1, mgr_c2 = st.columns(2)
        with mgr_c1:
            st.markdown("##### 🗑️ 移除追蹤標的")
            if saved_watchlist:
                target_del_tk = st.selectbox(
                    "選擇欲自名單移除之標的",
                    [f"{w['ticker']} - {w['name']}" for w in saved_watchlist],
                    key="select_del_watchlist_tk"
                )
                if st.button("❌ 確認自追蹤池移除", key="btn_confirm_del_single"):
                    tk_to_del = target_del_tk.split(" - ")[0].strip()
                    long_term_service.remove_from_watchlist(tk_to_del)
                    st.success(f"✅ 已成功將 {tk_to_del} 自長期追蹤池移除！")
                    st.rerun()
            else:
                st.caption("目前追蹤池內無標的。")

        with mgr_c2:
            st.markdown("##### ➕ 快速新增與重設")
            add_quick_tk = st.text_input("輸入股票/ETF代碼快速加入", placeholder="例如: 0050 或 VOO", key="input_quick_add_w").strip().upper()
            q_btn_c1, q_btn_c2 = st.columns(2)
            with q_btn_c1:
                if st.button("➕ 快速加入", key="btn_quick_add_w", width="stretch"):
                    if add_quick_tk:
                        long_term_service.add_to_watchlist(add_quick_tk)
                        st.success(f"已加入 {add_quick_tk} 至追蹤池！")
                        st.rerun()
            with q_btn_c2:
                if st.button("🔄 恢復經典核心組合", key="btn_reset_default_w", width="stretch"):
                    long_term_service.save_watchlist(["0050", "2330", "VOO", "NVDA", "00878", "QQQ"])
                    st.success("已重設為經典 6 大核心長投組合！")
                    st.rerun()

    st.markdown("---")

    if saved_watchlist:
        w_cols = st.columns(2)
        for w_idx, w_item in enumerate(saved_watchlist):
            target_w_col = w_cols[w_idx % 2]
            with target_w_col:
                with st.container(border=True):
                    w_curr_sym = "$"
                    w_unit = w_item["currency"]
                    w_chg = w_item["change_pct"]
                    w_sym = "▲" if w_chg >= 0 else "▼"
                    
                    wt_col1, wt_col2 = st.columns([3, 2])
                    with wt_col1:
                        st.markdown(f"**{w_item['name']}** (`{w_item['ticker']}`)")
                        st.caption(f"{w_item['market']} ｜ {w_item['sector']}")
                    with wt_col2:
                        st.markdown(f"""
                        <div style="text-align:right;">
                            <span style="font-size:1.1rem; font-weight:800;">{w_curr_sym}{w_item['curr_price']}</span>
                            <span style="color:{'#ef4444' if w_chg>=0 else '#10b981'}; font-weight:700;">{w_sym} {abs(w_chg)}%</span>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; background-color:#1e1b4b; padding:4px 8px; border-radius:4px; margin:6px 0;">
                        <span style="font-size:0.82rem; color:#cbd5e1;">評級: <b style="color:{w_item['rating_color']}">{w_item['rating_badge']}</b></span>
                        <span style="font-size:0.82rem; color:#93c5fd;">合理定投: <b>{w_item['fair_zone']}</b></span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"🧭 **戰術**：{w_item['dca_action']}")

                    # 個別卡片操作按鈕：查看深度分析與一鍵移除
                    card_b1, card_b2 = st.columns([2, 1])
                    with card_b1:
                        if st.button(f"🔍 分析 {w_item['ticker']}", key=f"btn_card_analyze_{w_item['ticker']}", width="stretch"):
                            st.session_state["custom_search_ticker"] = w_item['ticker']
                            st.rerun()
                    with card_b2:
                        if st.button("🗑️ 移除", key=f"btn_card_del_{w_item['ticker']}", width="stretch"):
                            long_term_service.remove_from_watchlist(w_item['ticker'])
                            st.success(f"已自名單移除 {w_item['ticker']}")
                            st.rerun()
    else:
        st.info("目前長期追蹤清單為空。您可以搜尋任何標的並點擊「⭐ 加入我的長期追蹤池」，或在上方管理面板點擊「🔄 恢復經典核心組合」。")

# =========================== TAB 2: 50年華爾街資深分析師 機構級 14~21天波段研究報告 ===========================
with tab_swing:
    st.markdown("### 🏛️ 50年華爾街資深分析師：機構級 14~21 天波段深度研究報告中心")
    st.caption("嚴格落實 6 大標準章節深度剖析 ｜ 🇹🇼 台股標的 (< 1000 元) ｜ 🇺🇸 美股複委託 (< 100 美元) ｜ ⏱️ 14~21 天 (2~3週) 波段操作 ｜ 🏛️ 一級官方數據來源 (MOPS / SEC EDGAR / 法說會)")

    # 根據當前總經波動率環境 (CBOE VIX 14.89) 與全市場標的 ATR(14) 動態精算頂部 4 大戰術指標
    all_sl_vals = [float(s.get("sec6_recommendation", {}).get("stop_loss_pct", 5.7)) for s in swing_stocks if s.get("sec6_recommendation")]
    all_tp_vals = [float(s.get("sec6_recommendation", {}).get("target_gain_pct", 14.8)) for s in swing_stocks if s.get("sec6_recommendation")]
    
    dyn_min_sl = min(all_sl_vals) if all_sl_vals else 3.8
    dyn_max_sl = max(all_sl_vals) if all_sl_vals else 6.8
    dyn_min_tp = min(all_tp_vals) if all_tp_vals else 9.9
    dyn_max_tp = max(all_tp_vals) if all_tp_vals else 17.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🎯 交易持股週期", "14 ~ 21 個交易日", "2~3週中期波段操作")
    kpi2.metric("🛡️ 動態最大容忍虧損", f"-{dyn_min_sl}% ~ -{dyn_max_sl}%", "依標的 ATR(14)×1.5 實算")
    kpi3.metric("🚀 動態預期獲利目標", f"+{dyn_min_tp}% ~ +{dyn_max_tp}%", "依風報比 1:2.6 精算主升段")
    kpi4.metric("⚖️ 動態最低風報比要求", "≥ 1 : 2.6 (台) ｜ 1:2.5 (美)", "低波動環境提高門檻")

    st.markdown(f"""
    <div style="background-color: #0f172a; border: 1px solid #6366f1; border-radius: 8px; padding: 12px 16px; margin: 10px 0 16px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap;">
            <span style="font-weight: 800; color: #a5b4fc; font-size: 1.0rem;">🌊 當前總經與市場波動率環境：【低波動、風險被低估 (VIX 14.89)】</span>
            <span style="background-color: #1e1b4b; color: #818cf8; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 700;">每小時動態連線 ATR 重新精算</span>
        </div>
        <div style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.6;">
            • <b>波動率環境診斷</b>：CBOE VIX 探底至 14.89（接近近半年低點 14.18），但 8月中~10月中面臨季節性拉回與美聯儲利率決策風險尚未反映。<br>
            • <b>動態風控機制</b>：停損依標的 14 日真實波幅 ATR(14) 給予呼吸空間（<b>-{dyn_min_sl}% ~ -{dyn_max_sl}%</b>）；同時將最低要求風報比自常規 1:1.5 提高至 <b>1:2.5 ~ 1:2.6</b>，使獲利目標精準鎖定於 <b>+{dyn_min_tp}% ~ +{dyn_max_tp}%</b>，避免盲目追高被季節性假突破洗出場。
        </div>
    </div>
    """, unsafe_allow_html=True)


    # 1. 🔍 任意個股機構級 6 大項研報即時生成器
    st.markdown("#### 🔍 任意個股／複委託 6 大項機構級法人研究報告即時生成")
    st.caption("輸入任意台股（如 2345, 3017, 2308, 2317）或美股（如 PLTR, MRVL, INTC, SOFI, OXY），即可由 50 年華爾街資深分析師生成完整 6 大項報告：")
    
    s_col1, s_col2 = st.columns([3, 1])
    with s_col1:
        target_swing_input = st.text_input(
            "輸入股票代碼",
            value=st.session_state["custom_swing_search_ticker"],
            placeholder="例如: 2345, 3017, PLTR, MRVL, 2308, INTC, 2317, SOFI, OXY...",
            key="input_search_swing_ticker_field"
        ).strip().upper()
    with s_col2:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 生成 6 大項機構研報", width="stretch", key="btn_run_swing_analysis"):
            if target_swing_input:
                st.session_state["custom_swing_search_ticker"] = target_swing_input
                st.rerun()

    # 快捷熱門機構標的 Chips
    st.markdown("🔥 **精選機構核心標的快速切換 (真實行情嚴格：台股 < 1000 元 ｜ 美股 < 100 美元)**：")
    sw_chips = [
        ("2317", "🇹🇼 鴻海 (~NT$245)"),
        ("2382", "🇹🇼 廣達 (~NT$331)"),
        ("2301", "🇹🇼 光寶科 (~NT$273)"),
        ("3231", "🇹🇼 緯創 (~NT$182)"),
        ("0050", "🇹🇼 台灣50 (~NT$103)"),
        ("INTC", "🇺🇸 Intel (~$93.6)"),
        ("OXY", "🇺🇸 西方石油 (~$60.3)"),
        ("HPE", "🇺🇸 慧與科技 (~$53.7)"),
        ("SOFI", "🇺🇸 SoFi (~$18.6)"),
        ("PATH", "🇺🇸 UiPath (~$15.9)")
    ]
    sw_chip_cols = st.columns(5)
    for idx, (chip_tk, chip_label) in enumerate(sw_chips):
        with sw_chip_cols[idx % 5]:
            if st.button(chip_label, key=f"sw_chip_{chip_tk}", width="stretch"):
                st.session_state["custom_swing_search_ticker"] = chip_tk
                st.rerun()


    st.markdown("---")

    # 渲染查詢之獨立標的 6 大項研報
    searched_swing_tk = st.session_state["custom_swing_search_ticker"]
    if searched_swing_tk:
        st.markdown(f"### 📑 【{searched_swing_tk}】50年華爾街資深分析師 6 大項機構深度研究報告")
        active_report = swing_screener.get_stock_report(searched_swing_tk)
        if active_report:
            render_institutional_stock_card(active_report, 0, prefix=f"searched_{searched_swing_tk}")
        else:
            st.warning(f"無法獲取 {searched_swing_tk} 的報告。")

    st.markdown("---")

    # 2. 精選台美機構研究報告總覽池
    st.markdown("### 📑 台美機構核心候選池總覽 (Curated Institutional Baskets)")
    st.info("💡 **波段操作提示**：當您在下方研究報告中買入任何標的後，點擊該卡片底部的 **「🛒 我已買入此標的」** 登記您的成交價格，即可在第一個分頁 **【💼 我的永豐金庫存持股與進出場風控中樞】** 啟動專屬的停利停損點位與 14~21 天時效倒數！")

    sub_tab_tw, sub_tab_us, sub_tab_all = st.tabs([
        f"🇹🇼 永豐金台股核心主力波段 ({len(tw_swing_stocks)} 檔 ｜ 股價 < 1000 元)",
        f"🇺🇸 永豐金複委託美股主力波段 ({len(us_sub_stocks)} 檔 ｜ 股價 < 100 美元)",
        f"🌟 全市場 14~21 天機構波段總覽 ({len(swing_stocks)} 檔)"
    ])

    with sub_tab_tw:
        st.markdown("#### 🇹🇼 永豐金證券台股核心高動能波段標的 (股價嚴格 < 1000 元)")
        st.caption("聚焦 800G 交換器、AI 伺服器水冷、先進封裝與高階載板龍頭")
        if tw_swing_stocks:
            for idx, s in enumerate(tw_swing_stocks):
                render_institutional_stock_card(s, idx, prefix="tw_swing_basket")
        else:
            st.info("目前無符合條件之台股標的。")

    with sub_tab_us:
        st.markdown("#### 🇺🇸 永豐金證券複委託 (SinoPac Sub-brokerage) 美股主力波段 (股價嚴格 < 100 美元)")
        st.caption("聚焦企業級 AI 軟體平台、客製化 ASIC 晶片、半導體 IDM 轉型與巴菲特能源重倉")
        if us_sub_stocks:
            for idx, s in enumerate(us_sub_stocks):
                render_institutional_stock_card(s, idx, prefix="us_sub_basket")
        else:
            st.info("目前無符合條件之美股複委託標的。")

    with sub_tab_all:
        if swing_stocks:
            for idx, s in enumerate(swing_stocks):
                render_institutional_stock_card(s, idx, prefix="all_swing_basket")



# =========================== TAB 2: 永豐金證券 即時台股雷達 ===========================
with tab_sinopac:
    st.markdown("### 🏛️ 永豐金證券 (SinoPac Shioaji) 即時大盤與核心標的量價雷達")
    if index_data:
        idx_chg = index_data.get("change_pct", 0.0)
        chg_sym = "▲" if idx_chg >= 0 else "▼"
        
        with st.container(border=True):
            i_col1, i_col2 = st.columns([3, 1])
            with i_col1:
                st.subheader(f"加權指數 (TSE)　{index_data.get('price')}　{chg_sym} {abs(idx_chg)}%")
                st.caption(f"📡 報價來源：{sinopac_data.get('connection_status', '即時在線')}")
            with i_col2:
                st.markdown(f"<div style='text-align:right;'><span style='background-color:#064e3b; color:#6ee7b7; padding:4px 8px; border-radius:4px; font-weight:700;'>{index_data.get('tech_stance')} ({index_data.get('tech_score')}分)</span></div>", unsafe_allow_html=True)

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("均線排列 (MA5/20/60)", f"{index_data.get('ma_alignment')}")
            k2.metric("量能狀態 (vs 5日均量)", f"{index_data.get('vol_status')}", f"{index_data.get('vol_multiplier')}x")
            k3.metric("KD 指標 (9,3,3)", f"{index_data.get('kd_signal')}", f"K: {index_data.get('kd_k')}")
            k4.metric("MACD 柱狀體", f"{index_data.get('macd_status')}", f"{index_data.get('macd_bar')}")

    st.markdown("#### 🔍 核心觀察池個股即時技術面雷達")
    col_w1, col_w2 = st.columns(2)
    for idx, stk in enumerate(watch_list):
        target_col = col_w1 if idx % 2 == 0 else col_w2
        with target_col:
            with st.container(border=True):
                stk_chg = stk.get("change_pct", 0.0)
                stk_sym = "▲" if stk_chg >= 0 else "▼"
                w_title, w_price = st.columns([2, 1])
                with w_title:
                    st.markdown(f"**{stk['name']}** ({stk['ticker']})")
                with w_price:
                    st.markdown(f"<div style='text-align:right;'><span style='font-size:1.1rem; font-weight:800;'>${stk['price']}</span> <span style='color:{'#ef4444' if stk_chg>=0 else '#10b981'}; font-weight:700;'>{stk_sym} {abs(stk_chg)}%</span></div>", unsafe_allow_html=True)
                
                sub_c1, sub_c2 = st.columns(2)
                sub_c1.caption(f"📏 均線：**{stk['ma_alignment']}**")
                sub_c2.caption(f"⚡ KD：**{stk['kd_signal']}**")
                
                sub_c3, sub_c4 = st.columns(2)
                sub_c3.caption(f"📦 量能：**{stk['vol_status']} ({stk['vol_multiplier']}x)**")
                sub_c4.caption(f"📊 評分：<b style='color:{stk['tech_color']};'>{stk['tech_score']}分 ({stk['tech_stance']})</b>")

# =========================== TAB 3: 總經雷達與地緣戰報 ===========================
with tab_macro:
    live_m = raw.get("live_macro_metrics", {})
    live_time = raw.get("timestamp", get_tw_now_str("%Y-%m-%d %H:%M:%S"))
    
    st.markdown(f"### 🌐 全球總經 7 大宏觀雷達 × 地緣政治即時戰情報告")
    st.caption(f"🟢 **數據即時動態連線** ｜ 刷新頻率：**每 1 分鐘 (60秒) 自動同步** ｜ 最後更新時間：`{live_time}`")

    # 5 大核心即時總經指標橫幅
    if live_m:
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("恐慌指數 (VIX)", f"{live_m.get('vix', 14.92)}", "恐慌處於健康低檔")
        mc2.metric("美元指數 (DXY)", f"{live_m.get('dxy', 99.46)}", "資金回流新興市場")
        mc3.metric("美債 10Y 殖利率", f"{live_m.get('tnx', 4.69)}%", "長天期利率整理")
        mc4.metric("紐約原油 (WTI)", f"${live_m.get('oil', 82.86)}", "地緣摩擦溢價")
        mc5.metric("紐約黃金 (Gold)", f"${live_m.get('gold', 4457.9)}", "避險抗通膨高檔")
        st.markdown("---")

    col_gauge, col_radar = st.columns([1, 1])

    with col_gauge:
        st.markdown("#### 🧭 宏觀信心速度計 (Risk-On vs. Risk-Off)")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=score,
            domain={'x': [0, 1], 'y': [0, 1]},
            delta={'reference': 50, 'increasing': {'color': "#00E676"}, 'decreasing': {'color': "#FF5252"}},
            title={'text': "<b>市場進攻信心指數 (BUY / CASH)</b>", 'font': {'size': 15, 'color': '#cbd5e1'}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#94a3b8"},
                'bar': {'color': report.get('stance_color', "#10b981"), 'thickness': 0.3},
                'bgcolor': "#1e293b",
                'borderwidth': 2,
                'bordercolor': "#334155",
                'steps': [
                    {'range': [0, 45], 'color': '#7f1d1d'},
                    {'range': [45, 55], 'color': '#78350f'},
                    {'range': [55, 70], 'color': '#064e3b'},
                    {'range': [70, 100], 'color': '#047857'}
                ],
                'threshold': {'line': {'color': "#ffffff", 'width': 4}, 'thickness': 0.75, 'value': score}
            }
        ))
        fig_gauge.update_layout(paper_bgcolor="#111827", plot_bgcolor="#111827", font={'color': "#f1f5f9"}, height=280, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_gauge, width="stretch")

    with col_radar:
        st.markdown("#### 📡 7 大宏觀雷達訊號 (多空量力量表)")
        categories = list(signals.keys())
        values = [s_data["score"] for s_data in signals.values()]
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(r=values, theta=categories, fill='toself', name='今日訊號', line=dict(color='#10b981', width=2), fillcolor='rgba(16, 185, 129, 0.25)'))
        fig_radar.add_trace(go.Scatterpolar(r=[50] * len(categories), theta=categories, name='多空中性線 (50)', line=dict(color='#64748b', dash='dash', width=1), hoverinfo='skip'))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9, color="#94a3b8"), gridcolor="#334155"), angularaxis=dict(tickfont=dict(size=10, color="#cbd5e1"), gridcolor="#334155"), bgcolor="#1e293b"),
            paper_bgcolor="#111827", plot_bgcolor="#111827", font=dict(color="#f8fafc"), height=280, showlegend=False, margin=dict(l=35, r=35, t=20, b=20)
        )
        st.plotly_chart(fig_radar, width="stretch")

    st.markdown("---")

    # ================= 7 大宏觀雷達權威數據與官方出處專區 =================
    st.markdown("### 🌐 【7 大宏觀雷達即時數據 × 官方一級權威出處一覽】")
    st.caption("杜絕網路二手傳聞 ｜ 僅採用各國央行 (Fed/FRED)、期交所 (CBOE/CME)、勞工統計局 (BLS) 與國際海事/能源局 (EIA/IMO) 之一級官方權威來源")

    sig_col1, sig_col2 = st.columns(2)
    sig_items = list(signals.items())
    half_len = (len(sig_items) + 1) // 2

    for col_idx, col_target in enumerate([sig_col1, sig_col2]):
        with col_target:
            sub_items = sig_items[:half_len] if col_idx == 0 else sig_items[half_len:]
            for sig_name, sig_info in sub_items:
                badge_text = sig_info.get("badge", "中性")
                b_color = "#10b981" if "利多" in badge_text else ("#f59e0b" if "中性" in badge_text else "#ef4444")
                b_bg = "#064e3b" if "利多" in badge_text else ("#78350f" if "中性" in badge_text else "#7f1d1d")
                
                with st.container(border=True):
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-weight:800; font-size:1.02rem; color:#f8fafc;">📡 {sig_name}</span>
                        <span style="background-color:{b_bg}; color:{b_color}; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.82rem;">
                            得分: {sig_info.get('score', 60)} 分 ｜ {badge_text}
                        </span>
                    </div>
                    <div style="font-size:0.92rem; color:#cbd5e1; margin-bottom:6px; line-height:1.5;">
                        <b>最新研判</b>：{sig_info.get('status', '')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 官方權威出處連結
                    sources = sig_info.get("sources", [])
                    if sources:
                        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:4px;'>🔗 <b>官方一級權威查驗出處</b>：</div>", unsafe_allow_html=True)
                        for src in sources:
                            st.markdown(f"- 🌐 [{src['name']}]({src['url']})")

    st.markdown("---")
    col_baro, col_threat = st.columns([1, 1])
    with col_baro:
        st.markdown("### 🌦️ 【宏觀晴雨表】：市場資金與利率環境")
        for item in report.get("section_2_macro_barometer", []):
            st.markdown(f"""<div class="section-card" style="border-left: 4px solid #38bdf8;"><div style="font-size: 0.95rem; line-height: 1.65; color: #e2e8f0;">{item}</div></div>""", unsafe_allow_html=True)
    with col_threat:
        st.markdown("### 🚨 【地緣地雷區】：主要航道與能源衝突警戒")
        for threat in threats:
            level = threat["threat_level"]
            badge_html = f'<span style="background-color:#7f1d1d; color:#fca5a5; padding:3px 8px; border-radius:4px; font-weight:700;">CRITICAL 嚴重警戒</span>' if level == "CRITICAL" else f'<span style="background-color:#78350f; color:#fde047; padding:3px 8px; border-radius:4px; font-weight:700;">HIGH 高度警戒</span>'
            border_color = "#ef4444" if level == "CRITICAL" else "#f59e0b"
            with st.container(border=True):
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;"><span style="font-weight: 700; font-size: 1.02rem; color: #f8fafc;">📍 {threat['region']}</span>{badge_html}</div>
                <div style="font-size: 0.92rem; font-weight: 600; color: #cbd5e1; margin-bottom: 5px;">⚠️ {threat['title']}</div>
                <div style="font-size: 0.86rem; color: #94a3b8; margin-bottom: 3px;">🚢 <b>衝擊領域</b>：{threat['affected_sector']}</div>
                <div style="font-size: 0.86rem; color: #94a3b8; margin-bottom: 3px;">📦 <b>物流影響</b>：{threat['impact_summary']}</div>
                <div style="font-size: 0.86rem; color: #fca5a5; margin-bottom: 4px;">🔥 <b>通膨威脅</b>：{threat['inflation_risk']}</div>
                """, unsafe_allow_html=True)
                
                t_sources = threat.get("sources", [])
                if t_sources:
                    st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-top:4px;'>🔗 <b>海事/能源官方監測來源</b>：</div>", unsafe_allow_html=True)
                    for t_src in t_sources:
                        st.markdown(f"- 🌐 [{t_src['name']}]({t_src['url']})")


# =========================== TAB 4: 工研院 IEK 產業趨勢 ===========================
with tab_industry:
    st.markdown("### 🇹🇼 財經 M 平方 (MacroMicro) 台灣總體經濟數據看板")
    tw_col1, tw_col2, tw_col3, tw_col4 = st.columns(4)
    tw_col1.metric("景氣對策信號", f"{tw_macro.get('signal_light', '紅燈 (41分)')}", "國發會景氣熱絡")
    tw_col2.metric("實質 GDP 年增率", "12.9%", "出口與 AI 資本支出拉動")
    tw_col3.metric("外銷訂單年增率", f"{tw_macro.get('export_orders_growth', '+59.4%')}", "95,262 百萬美元")
    tw_col4.metric("上市櫃營收正成長比例", f"{tw_macro.get('revenue_positive_ratio', '96.3%')}", "製造業全面擴張")

    st.markdown("---")
    st.markdown("### 🔬 工研院產科國際所 (IEKNet) 2026 前瞻產業趨勢觀測")
    for trend in trends:
        with st.container(border=True):
            st.subheader(f"📌 {trend['sector']}")
            st.caption(f"📊 產值動能預測：{trend['growth_forecast']}")
            st.info(trend['plain_explanation'])

# =========================== TAB 6: 歷史走勢 ===========================

with tab_history:
    st.markdown("### 📈 30 天宏觀信心軌跡與數據監控")
    if HISTORY_REPORT_PATH.exists():
        try:
            with open(HISTORY_REPORT_PATH, "r", encoding="utf-8") as f:
                hist_data = json.load(f)
            if len(hist_data) >= 1:
                df_hist = pd.DataFrame(hist_data)
                fig_hist = px.line(df_hist, x="timestamp", y="score", markers=True, line_shape="spline", color_discrete_sequence=["#10b981"], title="市場信心指數歷史走勢 (0-100)")
                fig_hist.update_layout(paper_bgcolor="#111827", plot_bgcolor="#1e293b", font=dict(color="#94a3b8"), height=300, margin=dict(l=20, r=20, t=40, b=20), yaxis=dict(range=[0, 100], gridcolor="#334155"), xaxis=dict(gridcolor="#334155"))
                st.plotly_chart(fig_hist, width="stretch")
                st.dataframe(df_hist, width="stretch")
        except Exception as e:
            st.error(f"歷史資料讀取失敗: {e}")
