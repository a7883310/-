import json
import os
import io
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
    REFRESH_INTERVAL_MINUTES
)
from scheduler_daemon import run_daily_macro_pipeline
from notifier import send_desktop_notification
from long_term_strategy_service import LongTermStrategyService
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


# 注入 5 分鐘自動刷新 HTML Meta (300 秒) 與深色終端主題 CSS
st.markdown(f"""
<meta http-equiv="refresh" content="{REFRESH_INTERVAL_MINUTES * 60}">
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


# 每 60 秒自動高頻刷新畫面 (1 分鐘)
if st_autorefresh is not None:
    st_autorefresh(interval=60 * 1000, key="auto_refresher_macro_1min")


def load_report_data():
    """載入最新戰報資料 (自動感應每分鐘磁碟新戰報與即時刷新)"""
    file_mtime = 0
    if LATEST_REPORT_PATH.exists():
        try:
            file_mtime = LATEST_REPORT_PATH.stat().st_mtime
        except Exception:
            pass

    last_loaded_mtime = st.session_state.get("_last_report_mtime", 0)

    # 若磁碟檔案有更新，或 session_state 無資料，直接重載磁碟檔案
    if file_mtime > last_loaded_mtime or "current_report" not in st.session_state or not st.session_state["current_report"]:
        if LATEST_REPORT_PATH.exists():
            try:
                with open(LATEST_REPORT_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    st.session_state["current_report"] = data
                    st.session_state["_last_report_mtime"] = file_mtime
                    return data
            except Exception:
                pass
        fresh = run_daily_macro_pipeline(send_notification=False)
        st.session_state["current_report"] = fresh
        st.session_state["_last_report_mtime"] = file_mtime if file_mtime > 0 else 1
        return fresh

    return st.session_state["current_report"]


# 初始化 Session State
if "alert_msg" not in st.session_state:
    st.session_state["alert_msg"] = None
if "custom_search_ticker" not in st.session_state:
    st.session_state["custom_search_ticker"] = "0050"
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
stocks = report.get("stock_recommendations", {})
sinopac_data = report.get("sinopac_market_data", {})
index_data = sinopac_data.get("market_index", {})
watch_list = sinopac_data.get("watch_list", [])
swing_data = report.get("swing_trading", {})
swing_stocks = swing_data.get("stocks", [])
tw_swing_stocks = swing_data.get("tw_stocks", [])
us_sub_stocks = swing_data.get("us_sub_stocks", [])

# 長期投資服務
long_term_service = LongTermStrategyService()

# 若無拆分則從 all stocks 依市場屬性區分
if not tw_swing_stocks and swing_stocks:
    tw_swing_stocks = [s for s in swing_stocks if s.get("market") == "TW" or s.get("currency") == "TWD"]
    us_sub_stocks = [s for s in swing_stocks if s.get("market") == "US_SUB" or s.get("currency") == "USD"]

# =========================== 側邊欄控制台 ===========================
with st.sidebar:
    st.markdown("### 🎛️ 傳奇操盤室控制台")
    st.caption("50年華爾街征戰心法 × 長期價值投資 × 高動能波段")
    st.markdown("---")

    # ================= 📱 手機同步觀看 QR Code 專區 =================
    st.subheader("📱 手機同步觀看")
    
    # 檢查是否有 Cloudflare 遠端連線網址
    cf_file = Path(__file__).parent / "data" / "cloudflare_url.txt"
    cf_url = None
    if cf_file.exists():
        try:
            with open(cf_file, "r", encoding="utf-8") as f:
                cf_url = f.read().strip()
        except Exception:
            pass

    with st.expander("點擊展開手機 QR Code 與網址", expanded=True):
        if cf_url:
            st.success("🟢 **Cloudflare 外出安全通道已連線**")
            st.caption("出門在外（4G/5G）請用手機相機掃描下方條碼：")
            qr_cf = generate_qr_image(cf_url)
            st.image(qr_cf, caption="🌐 外出 4G/5G 專用 QR Code", width=180)
            st.code(cf_url, language="text")
            st.markdown("---")
            st.caption(f"🏠 家中/公司 Wi-Fi 內網網址：`{mobile_url}`")
        else:
            st.caption("🏠 **家中/公司同 Wi-Fi 觀看**：")
            qr_img = generate_qr_image(mobile_url)
            st.image(qr_img, caption="📱 手機相機掃描即刻開啟", width=180)
            st.code(mobile_url, language="text")
            st.info("💡 若要**出門在外用 4G/5G 觀看**，請在專案資料夾執行 `開啟外出手機連線(Cloudflare).bat` 即可！")

    st.markdown("---")
    st.write(f"📅 **情報時間**:\n`{report.get('summary_date', datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))}`")
    st.write(f"⏱️ **自動更新**: `每 {REFRESH_INTERVAL_MINUTES} 分鐘`")
    st.write(f"🛡️ **總體評級**: `{rating}`")
    st.write(f"🇹🇼 **台灣景氣**: `{tw_macro.get('signal_light', '紅燈 (41分)')}`")
    st.write(f"⚡ **波段鎖定**: `{len(tw_swing_stocks)} 檔台股 + {len(us_sub_stocks)} 檔複委託`")

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

    if st.session_state["alert_msg"]:
        msg_type, msg_text = st.session_state["alert_msg"]
        if msg_type == "success":
            st.success(msg_text)
        else:
            st.info(msg_text)

# =========================== 主面板 Header ===========================
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


def render_stock_card(s: dict, idx: int):
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
            st.markdown("##### 🏛️ 本標的引據之權威可信來源白名單 (Trusted Sources)：")
            for src in sources:
                st.markdown(f"- **[{src['category']}]** [{src['name']}]({src['url']})")

        st.write("")


# =========================== 分頁導覽 ===========================
tab_long_term, tab_swing, tab_sinopac, tab_macro, tab_industry, tab_stocks, tab_history = st.tabs([
    "🏛️ 【長期價值投資與定期定額策略 (自訂標的)】",
    "⚡ 【5~7天高動能波段交易 (台股+複委託)】",
    "🏛️ 【永豐金證券 即時台股雷達 (Shioaji)】",
    "🌐 【總經雷達與地緣戰報】",
    "🏭 【工研院 IEK 產業趨勢 × 台灣景氣】",
    "🚀 【台美精選投資標的 (Stock Picks)】",
    "📈 【歷史走勢與數據監控】"
])

# =========================== TAB 0: 長期價值投資與定期定額策略 (自訂標的) ===========================
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

# =========================== TAB 1: 5~7天高動能波段交易 (台股 + 永豐金複委託美股) ===========================
with tab_swing:
    st.markdown("### ⚡ 三維合流 5~7 天高動能波段交易戰情報告 (Swing Trading Strategy)")
    st.caption("內建三大鐵律：1) 嚴格數學【驗證鏈】杜絕幻覺 ｜ 2) 操盤手 5 步【思考鏈】歷程 ｜ 3) 僅採用官方一級【權威來源】 ｜ 🇹🇼 台股 + 🇺🇸 永豐金複委託美股")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🎯 交易持股週期", "5 ~ 7 個交易日", "高週轉波段衝刺")
    kpi2.metric("🛡️ 最大容忍虧損", "-3.5% ~ -5.5%", "嚴格破 20MA 停損")
    kpi3.metric("🚀 預期波段目標", "+8.0% ~ +15.0%", "鎖定主升段催化")
    kpi4.metric("⚖️ 最低風報比要求", ">= 1 : 2.5", "不對市場妥協")

    st.markdown("---")

    sub_tab_us, sub_tab_tw, sub_tab_all = st.tabs([
        f"🇺🇸 永豐金複委託美股主力波段 ({len(us_sub_stocks)} 檔)",
        f"🇹🇼 永豐金台股核心主力波段 ({len(tw_swing_stocks)} 檔)",
        f"🌟 全市場波段監控 ({len(swing_stocks)} 檔)"
    ])

    with sub_tab_us:
        st.markdown("#### 🇺🇸 永豐金證券複委託 (SinoPac Sub-brokerage) 美股高動能波段標的")
        st.caption("聚焦全球 AI 算力龍頭、ASIC 晶片、企業級 AI 軟體與納斯達克旗艦 ETF")
        if us_sub_stocks:
            for idx, s in enumerate(us_sub_stocks):
                render_stock_card(s, idx)
        else:
            st.info("目前無符合條件之美股複委託標的。")

    with sub_tab_tw:
        st.markdown("#### 🇹🇼 永豐金證券台股核心高動能波段標的")
        st.caption("聚焦 800G 交換器、AI 伺服器水冷、先進封裝與高階載板龍頭")
        if tw_swing_stocks:
            for idx, s in enumerate(tw_swing_stocks):
                render_stock_card(s, idx)
        else:
            st.info("目前無符合條件之台股標的。")

    with sub_tab_all:
        if swing_stocks:
            for idx, s in enumerate(swing_stocks):
                render_stock_card(s, idx)

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
    live_time = raw.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
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
        st.markdown("#### 📡 7 大宏觀雷達訊號")
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
            st.markdown(f"""
            <div class="section-card" style="border-left: 4px solid {border_color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;"><span style="font-weight: 700; font-size: 1.02rem; color: #f8fafc;">📍 {threat['region']}</span>{badge_html}</div>
                <div style="font-size: 0.92rem; font-weight: 600; color: #cbd5e1; margin-bottom: 5px;">⚠️ {threat['title']}</div>
                <div style="font-size: 0.86rem; color: #94a3b8; margin-bottom: 3px;">🚢 <b>衝擊領域</b>：{threat['affected_sector']}</div>
                <div style="font-size: 0.86rem; color: #94a3b8; margin-bottom: 3px;">📦 <b>物流影響</b>：{threat['impact_summary']}</div>
                <div style="font-size: 0.86rem; color: #fca5a5;">🔥 <b>通膨威脅</b>：{threat['inflation_risk']}</div>
            </div>
            """, unsafe_allow_html=True)

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

# =========================== TAB 5: 台美精選投資標的 ===========================
with tab_stocks:
    st.markdown("### 🎯 總經與 IEK 產業鏈連動：台股與美股精選標的")
    col_tw_stocks, col_us_stocks = st.columns(2)
    with col_tw_stocks:
        st.markdown("#### 🇹🇼 台灣精選個股 / ETF (台股核心池)")
        for stk in stocks.get("taiwan_stocks", []):
            with st.container(border=True):
                st.markdown(f"**{stk['name']}** ({stk['ticker']}) ｜ <span style='color:#34d399; font-weight:700;'>{stk['rating']}</span>", unsafe_allow_html=True)
                st.caption(f"🏷️ {stk['sector']} ｜ 定位：{stk['target_role']}")
                st.write(f"💡 {stk['plain_rationale']}")
                st.markdown(f"<div style='background-color:#0f172a; padding:6px 10px; border-radius:4px; font-size:0.85rem; color:#93c5fd;'>🧭 <b>操作戰術</b>：{stk['action_strategy']}</div>", unsafe_allow_html=True)
                st.write("")

    with col_us_stocks:
        st.markdown("#### 🇺🇸 美國精選個股 / ETF (複委託核心池)")
        for stk in stocks.get("us_stocks", []):
            with st.container(border=True):
                st.markdown(f"**{stk['name']}** ({stk['ticker']}) ｜ <span style='color:#34d399; font-weight:700;'>{stk['rating']}</span>", unsafe_allow_html=True)
                st.caption(f"🏷️ {stk['sector']} ｜ 定位：{stk['target_role']}")
                st.write(f"💡 {stk['plain_rationale']}")
                st.markdown(f"<div style='background-color:#0f172a; padding:6px 10px; border-radius:4px; font-size:0.85rem; color:#fde047;'>🧭 <b>操作戰術</b>：{stk['action_strategy']}</div>", unsafe_allow_html=True)
                st.write("")

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
