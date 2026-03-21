from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .config import RecommendationWeights, USE_CASE_PRESETS


@dataclass
class RecommendationResult:
    manufacturer: str
    score: float
    ranked_scores: Dict[str, float]
    use_case: str
    use_case_note: str
    score_breakdown: Dict[str, Dict[str, float]]
    reason: str


class RecommendationEngine:
    metric_keys = ("safety", "noise", "speed", "maintenance", "energy", "cost")
    manufacturer_profile = {
        "mitsubishi": {"safety": 0.92, "noise": 0.78, "speed": 0.88, "maintenance": 0.86, "energy": 0.82, "cost": 0.62},
        "hitachi": {"safety": 0.90, "noise": 0.84, "speed": 0.81, "maintenance": 0.87, "energy": 0.85, "cost": 0.64},
        "otis": {"safety": 0.86, "noise": 0.80, "speed": 0.90, "maintenance": 0.82, "energy": 0.78, "cost": 0.67},
        "toshiba": {"safety": 0.84, "noise": 0.74, "speed": 0.76, "maintenance": 0.72, "energy": 0.70, "cost": 0.71},
        "thyssenkrupp": {"safety": 0.88, "noise": 0.77, "speed": 0.83, "maintenance": 0.80, "energy": 0.75, "cost": 0.66},
        "westinghouse": {"safety": 0.79, "noise": 0.70, "speed": 0.72, "maintenance": 0.68, "energy": 0.63, "cost": 0.75},
        "montgomery": {"safety": 0.80, "noise": 0.71, "speed": 0.74, "maintenance": 0.69, "energy": 0.64, "cost": 0.73},
    }
    text_bias_rules = {
        "safety": ("安全", "事故", "安心", "emergency", "safety"),
        "noise": ("静か", "騒音", "noise", "quiet"),
        "speed": ("速度", "待ち時間", "混雑", "speed", "rush"),
        "maintenance": ("保守", "点検", "故障", "maintenance", "repair"),
        "energy": ("省エネ", "電力", "環境", "energy", "eco"),
        "cost": ("コスト", "予算", "価格", "cost", "budget"),
    }

    @staticmethod
    def _normalize(w: RecommendationWeights) -> RecommendationWeights:
        vals = [w.safety, w.noise, w.speed, w.maintenance, w.energy, w.cost]
        total = max(sum(vals), 1e-9)
        return RecommendationWeights(*[v / total for v in vals])

    def _resolve_weights(self, use_case: str, custom: RecommendationWeights | None, note: str) -> Dict[str, float]:
        w = self._normalize(custom if custom else USE_CASE_PRESETS.get(use_case, USE_CASE_PRESETS["office"]))
        wm = {"safety": w.safety, "noise": w.noise, "speed": w.speed, "maintenance": w.maintenance, "energy": w.energy, "cost": w.cost}
        text = (note or "").strip().lower()
        if text:
            for metric, keys in self.text_bias_rules.items():
                if any(k in text for k in keys):
                    wm[metric] += 0.03
            total = max(sum(wm.values()), 1e-9)
            wm = {k: v / total for k, v in wm.items()}
        return wm

    def recommend(
        self,
        probabilities: Dict[str, float],
        use_case: str = "office",
        weights: RecommendationWeights | None = None,
        use_case_note: str = "",
    ) -> RecommendationResult:
        weight_map = self._resolve_weights(use_case, weights, use_case_note)
        candidates = list(probabilities.keys()) or list(self.manufacturer_profile.keys())
        scores, breakdown = {}, {}
        for m in candidates:
            metrics = self.manufacturer_profile.get(m, self.manufacturer_profile["mitsubishi"])
            contrib = {k: weight_map[k] * metrics[k] for k in self.metric_keys}
            weighted = sum(contrib.values())
            ai_conf = probabilities.get(m, 0.0)
            domain_component = 0.7 * weighted
            ai_component = 0.3 * ai_conf
            final = domain_component + ai_component
            scores[m] = final
            breakdown[m] = {
                "domain_weighted": weighted,
                "ai_confidence": ai_conf,
                "domain_component": domain_component,
                "ai_component": ai_component,
                "final_score": final,
                **{f"contrib_{k}": v for k, v in contrib.items()},
                **{f"weight_{k}": v for k, v in weight_map.items()},
            }
        selected = max(scores, key=scores.get)
        return RecommendationResult(
            manufacturer=selected,
            score=scores[selected],
            ranked_scores=scores,
            use_case=use_case,
            use_case_note=use_case_note,
            score_breakdown=breakdown,
            reason=f"{selected} selected.",
        )

