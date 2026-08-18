import re
from typing import Dict, Any, List, Tuple


class NewsSentimentFilter:
    """
    消息面輿情檢測與重大風險過濾模組
    1. 掃描近 30 日重大公告與新聞
    2. 關鍵字黑名單檢測（掏空、違約、敗訴、財測下修、檢調搜索、經營權爭奪等）
    3. 產出情緒評分與一句話重點摘要
    """

    def __init__(self):
        # 負面高危險關鍵字黑名單 (觸發直接排除或標註高風險)
        self.negative_blacklist = [
            "掏空", "違約交割", "跳票", "專利訴訟敗訴", "敗訴", 
            "財測下修", "調降財測", "檢調搜索", "遭檢調", "經營權爭奪", 
            "董監改選爭議", "下市", "全額交割", "暫停交易", "處置股", 
            "裁員", "掏空資產", "違法吸金", "減資彌補虧損"
        ]

        # 正面驅動關鍵字
        self.positive_keywords = [
            "營收新高", "毛利率攀升", "獲利超預期", "擴產", "大單到手", 
            "通過認證", "外銷暴增", "新產品出貨", "庫存去化完畢", "法人買超"
        ]

    def analyze_stock_news(self, ticker: str, stock_name: str, news_list: List[str]) -> Dict[str, Any]:
        """
        分析單一標的的新聞情緒，回傳：
        - is_safe: 是否通過安全過濾 (bool)
        - sentiment_label: 正向 (Positive) / 中性 (Neutral) / 警戒排除 (Disqualified)
        - sentiment_score: -100 ~ +100
        - risk_flags: 觸發的負面關鍵字
        - summary: 一句話消息面簡評
        """
        combined_text = " ".join(news_list)
        
        # 1. 檢測負面關鍵字
        triggered_risks = []
        for word in self.negative_blacklist:
            if word in combined_text:
                triggered_risks.append(word)

        if triggered_risks:
            return {
                "is_safe": False,
                "sentiment_label": "🚨 警戒排除 (負面事件)",
                "sentiment_tag": "ALERT",
                "sentiment_color": "#ef4444",
                "sentiment_score": -80,
                "risk_flags": triggered_risks,
                "summary": f"新聞出現負面關鍵字：{', '.join(triggered_risks)}，不符合超跌反彈安全條件。"
            }

        # 2. 計算正面分數
        pos_hits = [w for w in self.positive_keywords if w in combined_text]
        score = min(len(pos_hits) * 35 + 20, 90) if pos_hits else 15

        if score >= 50:
            label = "🟢 正向偏多 (利多醞釀)"
            tag = "POSITIVE"
            color = "#10b981"
            summary = f"近 30 日無負面違規事件，受惠『{pos_hits[0] if pos_hits else '產業動能'}』等題材，市場情緒偏向正面。"
        else:
            label = "🟡 中性平靜 (無負面利空)"
            tag = "NEUTRAL"
            color = "#f59e0b"
            summary = "近 30 日無重大負面利空或法律糾紛，籌碼沈澱，等待基本面催化劑。"

        return {
            "is_safe": True,
            "sentiment_label": label,
            "sentiment_tag": tag,
            "sentiment_color": color,
            "sentiment_score": score,
            "risk_flags": [],
            "summary": summary
        }


if __name__ == "__main__":
    filter_svc = NewsSentimentFilter()
    sample_safe = filter_svc.analyze_stock_news("3035", "智原", ["智原受惠先進封裝大單到手", "營收表現穩定"])
    sample_risk = filter_svc.analyze_stock_news("9999", "某公司", ["傳出經營權爭奪與董監改選爭議"])
    print("安全測試:", sample_safe)
    print("風險測試:", sample_risk)
