from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from ml.models.baseline import heuristic_predict
from ml.models.random_forest import build_model
from ml.preprocessing.clean import FEATURES, clean_frame
from ml.preprocessing.features import split_features_target
from ml.preprocessing.validation import validate_frame
from ml.training.evaluate import evaluate_model
from ml.nowcasting.model import WeatherNowcastModel

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "ml" / "datasets" / "processed" / "flood_demo_training.csv"
ARTIFACT = ROOT / "ml" / "artifacts" / "flood_risk_model.pkl"
NOWCAST_ARTIFACT = ROOT / "ml" / "artifacts" / "weather_nowcast_model.pkl"


def synthetic_dataset(rows: int = 900) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    df = pd.DataFrame(
        {
            "rainfall_24h": rng.uniform(20, 240, rows),
            "rainfall_7d": rng.uniform(80, 720, rows),
            "elevation": rng.uniform(2, 24, rows),
            "drainage_score": rng.uniform(20, 92, rows),
            "population_density": rng.uniform(4000, 36000, rows),
            "historical_flood_count": rng.integers(0, 16, rows),
            "citizen_report_count": rng.integers(0, 9, rows),
        }
    )
    df["risk_score"] = df.apply(lambda row: heuristic_predict(row.to_dict()), axis=1)
    df["risk_score"] = (df["risk_score"] + rng.normal(0, 2.8, rows)).clip(0, 100)
    return df


def load_dataset() -> pd.DataFrame:
    if not DATASET.exists():
        DATASET.parent.mkdir(parents=True, exist_ok=True)
        synthetic_dataset().to_csv(DATASET, index=False)
    df = pd.read_csv(DATASET)
    validate_frame(df)
    return clean_frame(df)


def main():
    df = load_dataset()
    x, y = split_features_target(df)
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)
    model = build_model()
    model.fit(x_train, y_train)
    metrics = evaluate_model(model, x_test, y_test)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACT)
    print({"artifact": str(ARTIFACT), "features": FEATURES, "metrics": metrics, "data": "deterministic synthetic demo dataset"})
    
    # Also train / initialize the Weather Nowcast Model artifact
    nowcast_model = WeatherNowcastModel(artifact_path=NOWCAST_ARTIFACT)
    joblib.dump(nowcast_model, NOWCAST_ARTIFACT)
    print({"artifact": str(NOWCAST_ARTIFACT), "status": "Weather Nowcasting Model ready"})


if __name__ == "__main__":
    main()

