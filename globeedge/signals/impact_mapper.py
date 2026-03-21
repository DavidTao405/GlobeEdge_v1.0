"""ImpactMapper — 物理訊號 → 8 維 impact_vector 統一轉換。

每個維度的意義（對應 issue_dimensions）：
  0: 媒體信任度
  1: 社會安全感
  2: 身份認同
  3: 經濟焦慮度
  4: 政策支持度
  5: 資訊環境感知
  6: 群體凝聚度
  7: 外部威脅感知

設計原則：
  - 每個維度的影響方向有明確的社會科學依據
  - 數值有上限 [-1, 1]，避免單一事件主宰整個仿真
  - 長期效應用 decay_rate 控制，不直接修改 W
"""

N_DIMS = 8


def _clamp(v: list[float]) -> list[float]:
    """確保所有值在 [-1, 1] 之間。"""
    return [round(min(max(x, -1.0), 1.0), 3) for x in v]


class ImpactMapper:
    """所有物理訊號轉 impact_vector 的邏輯集中在此。"""

    @staticmethod
    def military_vessels(count: int) -> list[float]:
        """AIS 台海軍艦數量 → impact_vector。

        社會科學依據：軍艦出現 → 外部威脅感知升高，經濟焦慮升高，
        政策支持度下降（對現狀政策不滿），群體凝聚度略降（恐慌）。
        """
        t = min(count / 20, 1.0)
        return _clamp([0, 0, 0, t * 0.3, -t * 0.2, 0, -t * 0.1, t])

    @staticmethod
    def earthquake(magnitude: float) -> list[float]:
        """USGS 地震規模 → impact_vector。

        社會科學依據：地震 → 社會安全感下降，經濟焦慮升高（重建成本），
        政策支持度略降（質疑防災政策），群體凝聚度略降（恐慌）。

        magnitude 4.5 → 最低閾值，7.5 → 飽和
        """
        t = min(max(0, (magnitude - 4.5) / 3.0), 1.0)
        return _clamp([0, -t * 0.3, 0, t * 0.6, -t * 0.1, 0, -t * 0.2, 0])

    @staticmethod
    def military_flights(count: int, in_adiz: bool = False) -> list[float]:
        """adsb.lol 軍機偵測 → impact_vector。

        in_adiz=True 時威脅感知加成 1.5x。
        """
        t = min(count / 10, 1.0) * (1.5 if in_adiz else 1.0)
        t = min(t, 1.0)
        return _clamp([0, 0, 0, t * 0.2, -t * 0.15, 0, 0, t * 0.7])

    @staticmethod
    def gdelt_article(title: str, tone: float) -> list[float]:
        """GDELT 負面新聞 → impact_vector。

        根據標題關鍵字判斷影響維度：
          軍事衝突 → 外部威脅 + 經濟焦慮
          經濟類   → 經濟焦慮 + 政策支持度
          政治類   → 媒體信任度 + 政策支持度
        """
        intensity = min(abs(tone) / 10, 1.0)
        vector = [0.0] * N_DIMS
        title_l = title.lower()

        if any(w in title_l for w in
               ["military", "war", "attack", "軍", "攻", "衝突"]):
            vector[7] += intensity * 0.8   # 外部威脅感知
            vector[3] += intensity * 0.3   # 經濟焦慮

        if any(w in title_l for w in
               ["economy", "stock", "trade", "經濟", "股", "貿易"]):
            vector[3] += intensity * 0.6   # 經濟焦慮
            vector[4] -= intensity * 0.2   # 政策支持度

        if any(w in title_l for w in
               ["election", "government", "policy", "選", "政", "政策"]):
            vector[0] -= intensity * 0.4   # 媒體信任度
            vector[4] += intensity * 0.2   # 政策支持度

        return _clamp(vector)
