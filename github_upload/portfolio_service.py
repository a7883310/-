"""
永豐金證券個人庫存與即時損益監控服務 (SinoPac Portfolio & Position Radar)
支援：
1. 永豐金 Shioaji API 實盤帳戶部位自動同步
2. 個人真實持股管理 (精確計算持股股數、買進成本、即時現價、未實現損益)
3. 5~7 天波段交易策略停損停利自動比對與風險預警
"""

import json
import os
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from config import (
    SHIOAJI_API_KEY,
    SHIOAJI_SECRET_KEY,
    SHIOAJI_SIMULATION,
    DATA_DIR,
    ENV_FILE
)
try:
    from live_market_data import get_live_tw_stock_data, get_live_us_stock_data
except ImportError:
    try:
        from live_market_data import get_live_tw_stock_data
    except Exception:
        def get_live_tw_stock_data(ticker):
            return None
    def get_live_us_stock_data(ticker):
        return None

PORTFOLIO_FILE = DATA_DIR / "user_portfolio.json"


class PortfolioService:
    """永豐金證券個人庫存監控與損益服務"""

    def __init__(self, sino_service=None):
        self.sino_service = sino_service
        self._ensure_portfolio_file()

    def _ensure_portfolio_file(self):
        """確保持股設定檔存在 (若不存在則預設為空清單)"""
        if not PORTFOLIO_FILE.exists():
            self.save_portfolio([])

    def load_portfolio(self) -> List[Dict[str, Any]]:
        """讀取持股設定清單"""
        if PORTFOLIO_FILE.exists():
            try:
                with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def save_portfolio(self, holdings: List[Dict[str, Any]]) -> bool:
        """儲存持股設定清單"""
        try:
            with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
                json.dump(holdings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[持股儲存失敗]: {e}")
            return False

    def clear_all_positions(self) -> bool:
        """一鍵清空所有庫存資料"""
        return self.save_portfolio([])

    def sync_with_shioaji_api(self) -> Tuple[bool, str, int]:
        """從永豐金證券 Shioaji API 同步實盤真實庫存"""
        from sinopac_service import SinoPacDataService
        self.sino_service = SinoPacDataService()

        if not self.sino_service.is_connected:
            return False, f"永豐金 API 尚未連線 ({self.sino_service.connection_msg})，無法直接同步。", 0

        real_positions = self.sino_service.fetch_real_shioaji_positions()
        self.save_portfolio(real_positions)
        if not real_positions:
            return True, f"✅ 永豐金證券 API 與 CA 憑證已連線成功 ({self.sino_service.connection_msg})！已完成同步（目前券商伺服器持股部位為 0 筆/空倉）。", 0

        return True, f"✅ 成功從永豐金證券伺服器同步 {len(real_positions)} 檔真實庫存部位！", len(real_positions)

    def add_position(self, ticker: str, name: str, market: str, shares: int, cost_price: float, trade_type: str = "現股", note: str = "") -> bool:
        """新增或更新指定持股部位"""
        holdings = self.load_portfolio()
        ticker = ticker.strip().upper()
        name = name.strip() if name.strip() else ticker
        is_us = market == "US_SUB" or any(c.isalpha() for c in ticker)
        currency = "USD" if is_us else "TWD"
        market_code = "US_SUB" if is_us else "TW"
        lots = shares if is_us else int(shares // 1000)

        updated = False
        for h in holdings:
            if h["ticker"].upper() == ticker:
                h["name"] = name
                h["market"] = market_code
                h["currency"] = currency
                h["shares"] = int(shares)
                h["lots"] = lots
                h["cost_price"] = float(cost_price)
                h["trade_type"] = trade_type
                h["note"] = note
                updated = True
                break

        if not updated:
            holdings.append({
                "ticker": ticker,
                "name": name,
                "market": market_code,
                "currency": currency,
                "trade_type": trade_type,
                "shares": int(shares),
                "lots": lots,
                "cost_price": float(cost_price),
                "target_strategy": "5~7天高動能波段",
                "note": note
            })

        return self.save_portfolio(holdings)

    def delete_position(self, ticker: str) -> bool:
        """刪除指定持股部位"""
        holdings = self.load_portfolio()
        new_holdings = [h for h in holdings if h["ticker"].upper() != ticker.strip().upper()]
        return self.save_portfolio(new_holdings)

    def query_live_portfolio_status(self) -> Dict[str, Any]:
        """
        整合真實即時報價、持股市值、未實現損益、波段目標價與停損點比對：
        產出高維度持股風控戰情報告
        """
        holdings = self.load_portfolio()
        
        if not holdings:
            return {
                "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "positions_count": 0,
                "is_empty": True,
                "summary_twd": {
                    "market_value": 0.0,
                    "cost": 0.0,
                    "unrealized_pnl": 0.0,
                    "return_pct": 0.0
                },
                "summary_usd": {
                    "market_value": 0.0,
                    "cost": 0.0,
                    "unrealized_pnl": 0.0,
                    "return_pct": 0.0
                },
                "positions": [],
                "alert_triggers": []
            }

        analyzed_positions = []
        total_market_value_twd = 0.0
        total_cost_twd = 0.0
        total_pnl_twd = 0.0

        total_market_value_usd = 0.0
        total_cost_usd = 0.0
        total_pnl_usd = 0.0

        alert_triggers = []

        for h in holdings:
            ticker = str(h["ticker"]).strip().upper()
            name = h.get("name", ticker)
            market = h.get("market", "TW")
            shares = int(h.get("shares", 1000))
            cost_price = float(h.get("cost_price", 100.0))
            is_us = market == "US_SUB" or h.get("currency") == "USD"

            # 抓取即時真實行情
            if is_us:
                live = get_live_us_stock_data(ticker)
                curr_price = float(live["price"]) if live else cost_price
                change_pct = float(live["change_pct"]) if live else 0.0
                curr_unit = "USD"
            else:
                live = get_live_tw_stock_data(ticker)
                curr_price = float(live["price"]) if live else cost_price
                change_pct = float(live["change_pct"]) if live else 0.0
                curr_unit = "TWD"

            # 精確計算市值與損益
            market_val = round(curr_price * shares, 2)
            cost_val = round(cost_price * shares, 2)
            unrealized_pnl = round(market_val - cost_val, 2)
            return_pct = round((unrealized_pnl / max(cost_val, 0.01)) * 100, 2)

            # 累計總額
            if is_us:
                total_market_value_usd += market_val
                total_cost_usd += cost_val
                total_pnl_usd += unrealized_pnl
            else:
                total_market_value_twd += market_val
                total_cost_twd += cost_val
                total_pnl_twd += unrealized_pnl

            # 5~7 天波段交易策略連動
            target_price = round(cost_price * 1.128, 2)   # +12.8% 波段目標
            stop_loss_price = round(cost_price * 0.958, 2) # -4.2% 硬性停損

            dist_to_target = round(((target_price - curr_price) / max(curr_price, 0.01)) * 100, 1)
            dist_to_stop = round(((curr_price - stop_loss_price) / max(curr_price, 0.01)) * 100, 1)

            # 風險狀態判定
            if curr_price >= target_price:
                risk_badge = "🚀 觸及停利區 (+12.8%)"
                risk_status = "TAKE_PROFIT"
                risk_color = "#10b981"
                action_advice = "已達 5~7 天波段獲利目標，建議分批獲利了結或移動停利！"
                alert_triggers.append(f"【{name} ({ticker})】已達波段停利目標價 (${target_price})！目前獲利 +{return_pct}%！")
            elif curr_price <= stop_loss_price:
                risk_badge = "🛑 跌破停損價 (-4.2%)"
                risk_status = "STOP_LOSS"
                risk_color = "#ef4444"
                action_advice = "已觸及最大硬性停損限制，強烈建議嚴格執行平倉防守！"
                alert_triggers.append(f"⚠️【{name} ({ticker})】跌破硬性停損價 (${stop_loss_price})！目前虧損 {return_pct}%！")
            elif curr_price < cost_price and dist_to_stop <= 1.5:
                risk_badge = "⚠️ 逼近停損防守線"
                risk_status = "WARNING"
                risk_color = "#f59e0b"
                action_advice = "距離停損點僅剩不到 1.5%，嚴格監控 20MA 支撐強度。"
            elif return_pct >= 6.0:
                risk_badge = "🟢 強勢獲利奔跑中"
                risk_status = "PROFITING"
                risk_color = "#00E676"
                action_advice = "獲利擴大中，可上移保本停損點鎖定獲利。"
            else:
                risk_badge = "⚡ 正常波段持股中"
                risk_status = "NORMAL"
                risk_color = "#3b82f6"
                action_advice = "股價於進場區間內正常震盪，持股續抱。"

            analyzed_positions.append({
                "ticker": ticker,
                "name": name,
                "market": market,
                "currency": curr_unit,
                "trade_type": h.get("trade_type", "現股"),
                "shares": shares,
                "lots": h.get("lots", shares if is_us else int(shares // 1000)),
                "cost_price": cost_price,
                "current_price": curr_price,
                "change_pct": change_pct,
                "market_val": market_val,
                "cost_val": cost_val,
                "unrealized_pnl": unrealized_pnl,
                "return_pct": return_pct,
                "target_price": target_price,
                "stop_loss_price": stop_loss_price,
                "dist_to_target": dist_to_target,
                "dist_to_stop": dist_to_stop,
                "risk_badge": risk_badge,
                "risk_status": risk_status,
                "risk_color": risk_color,
                "action_advice": action_advice,
                "note": h.get("note", "")
            })

        total_return_pct_twd = round((total_pnl_twd / max(total_cost_twd, 0.01)) * 100, 2)
        total_return_pct_usd = round((total_pnl_usd / max(total_cost_usd, 0.01)) * 100, 2)

        return {
            "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "positions_count": len(analyzed_positions),
            "is_empty": False,
            "summary_twd": {
                "market_value": total_market_value_twd,
                "cost": total_cost_twd,
                "unrealized_pnl": total_pnl_twd,
                "return_pct": total_return_pct_twd
            },
            "summary_usd": {
                "market_value": total_market_value_usd,
                "cost": total_cost_usd,
                "unrealized_pnl": total_pnl_usd,
                "return_pct": total_return_pct_usd
            },
            "positions": analyzed_positions,
            "alert_triggers": alert_triggers
        }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    service = PortfolioService()
    report = service.query_live_portfolio_status()
    print("=== 個人持股狀態 ===")
    print(f"持股檔數: {report['positions_count']}")
    print(f"台股部位：總市值 ${report['summary_twd']['market_value']:,.1f} 元 ｜ 損益: ${report['summary_twd']['unrealized_pnl']:+,.1f}")
