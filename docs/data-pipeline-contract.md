# Data pipeline contract

The pipeline is metadata-first and never downloads or invents observations.
User-supplied data belongs below `data/` and is ignored by Git:

```text
data/
  raw/insat_l1c/
  raw/insat_qpe/
  raw/insat_cmv/
  raw/imdaa/single_level/
  raw/imdaa/pressure_level/
  raw/dem/
  interim/
  processed/
  datasets/
  reports/
```

Run the metadata registry and optional sample inspection from the repository
root:

```powershell
python -m ml.ingestion.batch_ingest --config config/data.yaml --inspect --all
python -m ml.ingestion.batch_ingest --config config/data.yaml --source insat_l1c --inspect
```

The registry records SHA-256, source product, file format, readability,
metadata, and rejection status. Re-running it is idempotent. Missing inputs
remain missing and are reported in `data/reports/ingestion_manifest.json`.

The common model grid is EPSG:4326, 0.05 degrees, 114 by 84 cells. Source
coordinates, native timestamps, units, quality flags, alignment offsets, and
validity masks must be retained when producing model-ready data. Continuous
variables may be resampled with documented methods; categorical masks require
nearest-neighbour resampling.

## Proxy targets and RF

Future QPE targets are explicitly satellite-derived proxies:

```python
from ml.preprocessing.proxy_target_builder import build_future_qpe_targets
```

Rows without complete future coverage are marked `UNUSABLE_MISSING_FUTURE` and
are not negatives. Confirmed labels must come from user-supplied authoritative
observations:

```powershell
python scripts/labels/build_labels.py --source-dir data/observations --output data/datasets/confirmed_labels.jsonl
```

Build a Parquet or CSV training dataset containing `issue_time`, a future
proxy `target`, and named features. Train only with an explicit target type:

```powershell
python -m ml.training.train --dataset data/datasets/flood_proxy.parquet `
  --features qpe_3h elevation slope --target-type classification `
  --artifact ml/artifacts/flood_random_forest.joblib
```

The trainer uses a chronological split and fits imputation inside an sklearn
pipeline on the training partition. It does not create demo data, fill
missing targets as negatives, or create a nowcasting artifact.

No claim of confirmed flood-event prediction is valid without independent
observations. A 90-day archive is insufficient evidence of generalization to
unseen events.
