from pathlib import Path
import joblib
from ml.models.baseline import category, heuristic_predict
from ml.preprocessing.clean import FEATURES
from ml.models.random_forest import build_model
import numpy as np
import pandas as pd


def _train_demo_and_persist(artifact: Path, random_state: int = 42):
    """Train a deterministic demo RandomForest on synthetic data and persist to artifact path."""
    rng = np.random.default_rng(random_state)
    rows = 900
    df = pd.DataFrame({
        "rainfall_24h": rng.uniform(20, 240, rows),
        "rainfall_7d": rng.uniform(80, 720, rows),
        "elevation": rng.uniform(2, 24, rows),
        "drainage_score": rng.uniform(20, 92, rows),
        "population_density": rng.uniform(4000, 36000, rows),
        "historical_flood_count": rng.integers(0, 16, rows),
        "citizen_report_count": rng.integers(0, 9, rows),
    })
    df["risk_score"] = df.apply(lambda row: heuristic_predict(row.to_dict()), axis=1)
    df["risk_score"] = (df["risk_score"] + rng.normal(0, 2.8, rows)).clip(0, 100)
    X = df[FEATURES].values
    y = df["risk_score"].values
    model = build_model(random_state=random_state)
    model.fit(X, y)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact)
    return model


ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "flood_risk_model.pkl"


class FloodRiskModel:
    def __init__(self):
        if ARTIFACT.exists():
            try:
                self.model = joblib.load(ARTIFACT)
            except Exception:
                # corrupted artifact — attempt to retrain
                self.model = _train_demo_and_persist(ARTIFACT)
        else:
            # If no artifact exists (e.g., fresh clone), create a deterministic demo model
            try:
                self.model = _train_demo_and_persist(ARTIFACT)
            except Exception:
                # If training fails due to missing packages at runtime, fall back to heuristic
                self.model = None

    def predict(self, features: dict) -> dict:
        row = {key: float(features.get(key, 0)) for key in FEATURES}
        if self.model is None:
            score = heuristic_predict(row)
            confidence = 0.72
        else:
            score = float(self.model.predict([[row[key] for key in FEATURES]])[0])
            score = round(max(0, min(100, score)), 1)
            confidence = 0.84
        return {"risk_score": score, "risk_category": category(score), "confidence": confidence}
