from ml.preprocessing.clean import FEATURES


def validate_frame(df):
    missing = [column for column in FEATURES + ["risk_score"] if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
