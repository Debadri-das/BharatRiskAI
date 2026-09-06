from ml.preprocessing.clean import FEATURES


def split_features_target(df):
    return df[FEATURES], df["risk_score"]
