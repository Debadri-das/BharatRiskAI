from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


def build_model(target_type: str = "regression", random_state: int = 42) -> Pipeline:
    if target_type not in {"classification", "regression"}:
        raise ValueError("target_type must be 'classification' or 'regression'")
    estimator = (
        RandomForestClassifier(n_estimators=160, min_samples_leaf=2, random_state=random_state, class_weight="balanced")
        if target_type == "classification"
        else RandomForestRegressor(n_estimators=160, min_samples_leaf=2, random_state=random_state)
    )
    return Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True)), ("model", estimator)])
