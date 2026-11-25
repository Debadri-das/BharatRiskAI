from pathlib import Path
import joblib
from ml.models.baseline import category


ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "flood_random_forest.joblib"


class FloodRiskModel:
    def __init__(self):
        self.model = None
        self.feature_columns = []
        if ARTIFACT.exists():
            loaded = joblib.load(ARTIFACT)
            if isinstance(loaded, dict) and "model" in loaded:
                self.model = loaded["model"]
                self.feature_columns = loaded.get("feature_columns", [])
            else:
                self.model = loaded

    def predict(self, features: dict) -> dict:
        if self.model is None:
            raise RuntimeError("No trained flood Random Forest artifact is available")
        columns = self.feature_columns or list(features)
        row = [{key: features[key] for key in columns}]
        if hasattr(self.model, "predict_proba"):
            score = float(self.model.predict_proba(row)[0][1] * 100)
        else:
            score = float(self.model.predict(row)[0])
        score = round(max(0, min(100, score)), 1)
        confidence = 0.84
        return {"risk_score": score, "risk_category": category(score), "confidence": confidence}
