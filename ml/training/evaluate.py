from ml.training.metrics import regression_metrics


def evaluate_model(model, x_test, y_test):
    return regression_metrics(y_test, model.predict(x_test))
