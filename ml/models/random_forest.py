from sklearn.ensemble import RandomForestRegressor


def build_model(random_state: int = 42):
    return RandomForestRegressor(n_estimators=160, min_samples_leaf=2, random_state=random_state)
