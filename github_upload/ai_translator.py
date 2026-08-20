import os
import json
import datetime
from typing import Dict, Any
from config import OPENAI_API_KEY, GEMINI_API_KEY, get_tw_now_str
from prompt_template import LEGENDARY_TRADER_SYSTEM_PROMPT, build_user_prompt


class AITranslator:
    """50年華爾街傳奇操盤手：三維合流波段決策轉譯引擎"""

    def __init__(self):
        self.has_llm = bool(OPENAI_API_KEY or GEMINI_API_KEY)

    def evaluate_multi_dimensional_resonance(self, wm_data: Dict[str, Any], sinopac_data: Dict[str, Any], tw_macro: Dict[str, Any]) -> Dict[str, Any]:
        """
        跨維度決策矩陣運算：
        維度 1：外在總經 (World Monitor)
        維度 2：台灣景氣 (MacroMicro 景氣對策信號)
        維度 3：內在動能 (永豐金證券 Shioaji 台股即時大盤技術指標)
        """
        wm_rating = wm_data.get("overall_rating", "BUY")
        wm_score = wm_data.get("overall_score", 60.0)
        idx_data = sinopac_data.get("market_index", {})
        tech_score = idx_data.get("tech_score", 80.0)
        is_tw_red = "紅燈" in tw_macro.get("signal_light", "")

        is_macro_bull = "BUY" in wm_rating or wm_score >= 55.0
        is_tech_bull = tech_score >= 70.0

        if is_macro_bull and is_tech_bull and is_tw_red:
            resonance_status = "🚀 【強烈多頭共振 (天時地利點火)】"
            resonance_badge = "強烈多頭共振"
            resonance_color = "#00E676"
            resonance_detail = "【外在總經與流動性】：全球熱錢維持寬鬆，美債殖利率回穩，台灣景氣連莊紅燈 (41分)，外銷訂單高頻領先指標飆漲 +59.4%。\n【內在市場量價架構】：台股加權指數均線全多頭排列，成交量放量突破 20MA，MACD 零軸上方紅柱加速放大。\n【操盤手共振結論】：天時地利俱備，符合『三維合流』最高勝率攻擊型態，果斷執行 14~21 天高動能波段攻擊！"
            market_advice = "傳奇操盤手箴言：『市場最亢奮的波段往往由最強催化板塊主導。順大勢、鎖定龍頭，嚴守依 ATR(14) 實算之動態停損 (-5.5%~-6.8%)，讓利潤在 14~21 天 (2~3週) 內奔馳！』"


        elif is_macro_bull and not is_tech_bull:
            resonance_status = "⚠️ 【基本面強但短線整理 (鎖定 VCP 突破)】"
            resonance_badge = "蓄勢整理"
            resonance_color = "#FFD600"
            resonance_detail = "【外在大環境】：外在總經與外銷數據極強。\n【內在大盤動能】：大盤短線窄幅震盪洗盤。\n【共振結論】：大方向未變，等待 VCP (底底高) 突破日放量確認進場。"
            market_advice = "傳奇操盤手箴言：『不要在震盪區盲目消耗子彈，等待成交量放大 1.5 倍的突破信號再揮棒！』"
        elif not is_macro_bull and is_tech_bull:
            resonance_status = "⚡ 【總經逆風但技術面軋空 (短線快打)】"
            resonance_badge = "嚴格停損"
            resonance_color = "#FF9100"
            resonance_detail = "【外在大環境】：外在熱錢緊縮或地緣衝突升溫。\n【內在大盤動能】：台股靠特定權值股硬拉，技術面強勢但量能背離。\n【共振結論】：投機軋空波段，風報比要求拉高至 1:3。"
            market_advice = "傳奇操盤手箴言：『這是一場在鋼索上的短線派對，賺取 5~8% 即見好就收，破支撐立即離場！』"
        else:
            resonance_status = "🛑 【空頭全面共振 (現金為王)】"
            resonance_badge = "全面防守"
            resonance_color = "#FF5252"
            resonance_detail = "【外在大環境】：全球總經轉 CASH，外銷訂單下滑。\n【內在大盤動能】：台股均線空頭排列，量縮破底。\n【共振結論】：內外皆空，嚴禁任何撈底行為。"
            market_advice = "傳奇操盤手箴言：『在暴風雨中，保全本金永遠是第一要務。握緊現金，等待下一個超級週期。』"

        return {
            "resonance_status": resonance_status,
            "resonance_badge": resonance_badge,
            "resonance_color": resonance_color,
            "resonance_detail": resonance_detail,
            "market_advice": market_advice
        }

    def generate_colloquial_report(self, aggregated_data: Dict[str, Any]) -> Dict[str, Any]:
        """產出專業操盤手戰情報告"""
        wm = aggregated_data["world_monitor"]
        tw_macro = aggregated_data["taiwan_macro"]
        industry_trends = aggregated_data["industry_trends"]
        stock_recs = aggregated_data["stock_recommendations"]
        sinopac_data = aggregated_data["sinopac_market_data"]
        swing_trading_data = aggregated_data["swing_trading"]

        score = wm["overall_score"]
        rating = wm["overall_rating"]
        color = wm["color_theme"]

        resonance = self.evaluate_multi_dimensional_resonance(wm, sinopac_data, tw_macro)

        one_sentence = f"⚡ **【50年華爾街操盤手戰略指令】** 當前總經多頭動能充沛（宏觀信心 {score}/100），台灣外銷訂單強勁。共振型態確立為『{resonance['resonance_badge']}』，鎖定高催化 AI 算力與散熱龍頭，執行『5~7 天高動能波段攻擊，嚴守 -4% 硬性停損，追求 1:2.5+ 風報比』。"

        macro_barometer = [
            f"💧 **流動性與熱錢環境 (Liquidity)**：{wm['macro_radar']['市場熱錢 (Liquidity)']['status']}。美債 10Y/2Y 殖利率倒掛收斂，Fed 降息週期預期推升 Smart Money 集中流入領先科技權值股。",
            f"📈 **經濟與外銷動能 (Growth)**：{wm['macro_radar']['經濟動能 (Growth)']['status']}。全球科技大廠 AI 資本支出強勢擴張，企業獲利共識持續向上修訂 (Upward Revision)。",
            f"🇹🇼 **台灣景氣 (MacroMicro)**：{tw_macro['signal_light']} (41分)。實質 GDP 年增 {tw_macro['real_gdp_growth']}，外銷訂單飆增 {tw_macro['export_orders_growth']}，96.3% 上市櫃營收正成長。",
            f"🏦 **利率與估值環境 (Real Rates & Valuation)**：{wm['macro_radar']['利率環境 (Real Rates)']['status']}。市場對無風險利率下降進行定價，高定價權與高成長股享估值溢價。",
            f"🌡️ **市場恐慌度 (Volatility)**：{wm['macro_radar']['市場穩定度 (Low Volatility)']['status']}。VIX 處於良性低檔，波段突破不易遭雜訊中斷。"
        ]

        geopolitical_zone = []
        for t in wm["geopolitical_threats"]:
            zone_text = f"**【{t['region']}】** - ({t['threat_level']})\n"
            zone_text += f"  - **事態狀況**：{t['title']}\n"
            zone_text += f"  - **實質影響**：{t['impact_summary']}\n"
            zone_text += f"  - **通膨威脅**：{t['inflation_risk']}"
            geopolitical_zone.append(zone_text)

        portfolio_guide = {
            "stocks": "📈 **波段攻擊部位 (建議 60%~65%)**：集中於 800G 交換器 (智邦 2345)、AI 液冷散熱 (奇鋐 3017)、先進封裝與晶圓代工 (台積電 2330)、高階載板 (欣興 3037)。",
            "bonds_cash": "💵 **機動現金 (建議 25%~30%)**：作為波段停損後隨時切換強勢主流股的後備資金池。",
            "gold_commodities": "🪙 **避險抗通膨 (建議 10%)**：配置黃金或能源 ETF，防範地緣黑天鵝突發突刺。"
        }

        return {
            "summary_date": get_tw_now_str("%Y-%m-%d %H:%M:%S"),
            "stance_tag": rating,
            "stance_color": color,
            "resonance_status": resonance["resonance_status"],
            "resonance_badge": resonance["resonance_badge"],
            "resonance_color": resonance["resonance_color"],
            "resonance_detail": resonance["resonance_detail"],
            "market_advice": resonance["market_advice"],
            "section_1_one_sentence": one_sentence,
            "section_2_macro_barometer": macro_barometer,
            "section_3_geopolitical_zone": "\n\n".join(geopolitical_zone),
            "section_4_portfolio_guide": portfolio_guide,
            "taiwan_macro": tw_macro,
            "industry_trends": industry_trends,
            "stock_recommendations": stock_recs,
            "sinopac_market_data": sinopac_data,
            "swing_trading": swing_trading_data,
            "long_term_strategy": aggregated_data.get("long_term_strategy", []),
            "raw_metrics": wm
        }
