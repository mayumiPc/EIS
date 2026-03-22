from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ai_engine import AIEngine, PredictionResult
from .config import ALL_CLASS_NAMES, ModelConfig, RecommendationWeights
from .recommendation_engine import RecommendationEngine, RecommendationResult


@dataclass
class AnalysisResult:
    prediction: PredictionResult
    recommendation: RecommendationResult


class EISController:
    def __init__(self) -> None:
        self._engines: dict[str, AIEngine] = {}
        self.recommendation_engine = RecommendationEngine()

    def _engine(self, model_type: str) -> AIEngine:
        key = "user" if model_type == "user" else "base"
        if key in self._engines:
            return self._engines[key]
        path = Path("models/eis_classifier_user.pt" if key == "user" else "models/eis_classifier_base.pt")
        if key == "base" and not path.exists() and Path("models/eis_classifier.pt").exists():
            path = Path("models/eis_classifier.pt")
        eng = AIEngine(ModelConfig(class_names=ALL_CLASS_NAMES, model_path=path))
        self._engines[key] = eng
        return eng

    def discard_user_engine_cache(self) -> None:
        """ユーザー学習モデルファイル削除後など、メモリ上の user エンジンを破棄する。"""
        self._engines.pop("user", None)

    def infer(self, file_path: str, model_type: str = "base") -> PredictionResult:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(file_path)
        eng = self._engine(model_type)
        if p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}:
            return eng.predict_video(p)
        return eng.predict_image(p)

    def recommend(
        self,
        use_case: str = "office",
        weights: RecommendationWeights | None = None,
        probabilities: dict[str, float] | None = None,
        use_case_note: str = "",
    ) -> RecommendationResult:
        return self.recommendation_engine.recommend(
            probabilities=probabilities or {},
            use_case=use_case,
            weights=weights,
            use_case_note=use_case_note,
        )

    def analyze(
        self,
        file_path: str,
        weights: RecommendationWeights | None = None,
        use_case: str = "office",
        model_type: str = "base",
        use_case_note: str = "",
    ) -> AnalysisResult:
        pred = self.infer(file_path=file_path, model_type=model_type)
        rec = self.recommend(
            use_case=use_case,
            weights=weights,
            probabilities=pred.probabilities,
            use_case_note=use_case_note,
        )
        return AnalysisResult(prediction=pred, recommendation=rec)

