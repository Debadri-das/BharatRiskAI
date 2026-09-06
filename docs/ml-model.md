# ML Model

The first model is a Random Forest regressor trained on:

- `rainfall_24h`
- `rainfall_7d`
- `elevation`
- `drainage_score`
- `population_density`
- `historical_flood_count`
- `citizen_report_count`

Run `python -m ml.training.train` to create a deterministic synthetic dataset when real data is missing, evaluate the model, and save `ml/artifacts/flood_risk_model.pkl`.

Synthetic data exists only to make the prototype runnable without paid services or unavailable datasets.
