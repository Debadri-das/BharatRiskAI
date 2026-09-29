# Runtime Architecture Audit

## Overview
This audit reviews the current components of the BharatRiskAI repository as requested in **MICROTASK 0**, identifying data sources, feature pipelines, model architectures, and inference pathways.

---

## Inspected Components

1. **`backend/services/nowcast_service.py`**
   - Orchestrates nowcasting for individual zones and citywide aggregation.
   - Currently uses `UnifiedFeaturePipeline` and `WeatherNowcastModel`.

2. **`ingestion/satellite_feeds.py` & `ingestion/real_data.py`**
   - Handles satellite feed extraction and physical conversions (e.g., cloud top temperature brightness temperature conversions).

3. **`ingestion/satellite.py`**
   - Contains Copernicus Sentinel-1 and `DemoSatelliteProvider` implementations.

4. **`scripts/insat/extract_l1c.py`**
   - Canonical decoder for INSAT-3DR L1C HDF5 products into standardized `.npz` files.

5. **`scripts/features/` (`satellite_features.py`, `qpe_features.py`, `dem_features.py`)**
   - Feature extraction scripts for various meteorological and geographical data sources.

6. **`scripts/preprocessing/align_datasets.py` & `scripts/datasets/build_sequences.py`**
   - Handles spatial/temporal alignment and multi-frame sequence construction.

7. **`ml/nowcasting/architecture.py` & `ml/nowcasting/inference.py`**
   - Contains `SpatiotemporalMTLNet` and `NowcastingInferenceEngine`.
   - Explicit checkpoint loading (`load_artifact`) and normalization loading (`load_normalization`) have been implemented.

8. **`scripts/training/train_multitask.py` & `ml/training/train.py`**
   - Training scripts enforcing determinism, multi-task focal loss, and saving checkpoints with metadata and normalization statistics.

---

## Findings & Status
- **Compilation**: All Python files in `backend`, `ingestion`, `ml`, `scripts`, and `worker` compile successfully.
- **Checkpoints & Data**: Real trained checkpoints (`models/checkpoints/best.pt`) and final processed dataset index (`data/datasets/final/index.csv`) are currently required to run production inference. Without them, pipelines report missing data/checkpoints as designed to prevent fake predictions.
