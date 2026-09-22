# BharatRiskAI Historical Data Pipeline

This pipeline is an AI nowcasting layer over observed satellite/reanalysis inputs. It does not replace NWP and does not claim confirmed hazard ground truth when source observations are absent. Observations, derived features, proxy labels, and model predictions are always kept distinct.

## Current audit

Run:

```powershell
python scripts/run_pipeline.py --stage audit
```

The current repository contains 48 usable INSAT-3DR L1C timestamps on 2023-07-01, one non-overlapping INSAT QPE sample from 2024-06-18, a Kolkata DEM, no IMDAA files, no CMV files, and no official thunderstorm, cloudburst, or flood observations. Seven nested L1C downloads are truncated and are recorded by `reports/data_audit.json` rather than silently used. Raw files are never modified.

## Stages

Run stages in this order (Windows/PowerShell):

```powershell
python scripts/run_pipeline.py --stage audit
python scripts/run_pipeline.py --stage extract
python scripts/run_pipeline.py --stage features
python scripts/run_pipeline.py --stage align
python scripts/run_pipeline.py --stage labels
python scripts/run_pipeline.py --stage validate
python scripts/run_pipeline.py --stage sequence
python scripts/run_pipeline.py --stage normalize
python scripts/run_pipeline.py --stage train
python scripts/run_pipeline.py --stage calibrate
python scripts/run_pipeline.py --stage thresholds
python scripts/run_pipeline.py --stage evaluate
```

`extract_l1c.py` reads provider projection metadata, crops the study region, applies radiance calibration and temperature/albedo lookup tables, and writes processed NPZ files. Corrupted/truncated granules are skipped with explicit error records. Raw files are never changed.

The common ML grid is EPSG:4326 at 0.05 degrees, 114 by 84 cells, with a 30-minute time contract. This is intentionally coarser than the 30 m DEM because the satellite channels are approximately 4 km resolution; the DEM's native 30 m resolution is never used as the ML resolution.

Satellite WV is stored as calibrated radiance and is never mislabeled as IWV. IMDAA processing derives IWV, CAPE, CIN, convergence, and shear only when real vertical-profile files are present, and fails loudly (no defaults) when IMDAA is absent. QPE 1h/3h/6h accumulations remain NaN when the required historical QPE timestamps are missing; missing observations are never interpolated as if measured. CMV features are documented as absent and the pipeline continues without them.

## Labels and training

`labels/build_labels.py` writes provenance-rich tri-state records with hazard, label, label_type, source, threshold, accumulation window, timestamp, spatial rule, confidence, and provenance. `null` means unknown, never negative. Thresholds come only from `config/labels.yaml`:

- `thunderstorm`: satellite-signature proxy (CTT proxy <= -40 C AND CTT-proxy cooling >= 2.0 C/hr on observed L1C features). Pixels without finite TIR1/cooling are unknown.
- `cloudburst`: QPE-rate proxy at the configured threshold (100 mm in 1 hour, conventional definition recorded in the config; pending authoritative confirmation).
- `flash_flood`: no threshold and no overlapping observations, so labels stay unknown. Rainfall alone is never flood truth; CAPE alone is never thunderstorm truth.

Current label counts (see `reports/label_statistics.json`): 0 confirmed labels; 47 thunderstorm proxy positives; 1 cloudburst proxy negative; 99 unknown records; 49 spatial label grids. Proxy labels are deterministic rules on observations and are never presented as observed events or as model output.

`datasets/build_sequences.py` requires spatial label grids and event/date-separated samples (target = history through T plus +2h..+6h horizons). It refuses to expand scalar labels into spatial truth, refuses random frame splits, and refuses to run while any target is unknown. With fewer than three independent event/date groups, no train/validation/test split is created. `training/fit_normalization.py` fits scalers on training samples only. Calibration fits temperature scaling on validation predictions only; threshold selection optimizes CSI on validation only; evaluation uses untouched test predictions with the validation-selected thresholds (never a default 0.5).

```powershell
python scripts/run_pipeline.py --stage sequence
python scripts/run_pipeline.py --stage normalize
python scripts/run_pipeline.py --stage train
python scripts/run_pipeline.py --stage calibrate
python scripts/run_pipeline.py --stage thresholds
python scripts/run_pipeline.py --stage evaluate
```

Current stage results (all intentional, reproducible hard stops):

| Stage | Result | Report |
|---|---|---|
| sequence | blocked: 99 unknown targets, <3 independent dates | `reports/data_readiness.md` / `.json` |
| validate | failed loudly: 7 corrupt files, 99 unknown labels, thunderstorm proxy has 0 negatives | `reports/dataset_validation.json` / `.html` |
| normalize | blocked: no final dataset index | stderr |
| train | blocked: no final dataset index | `reports/training_blocked.json` |
| calibrate | blocked: no validation predictions | `models/calibration/calibration_blocked.json`, `reports/calibration_report.json` |
| thresholds | blocked: no validation predictions; `config/alerts.yaml` thresholds stay null | `reports/threshold_selection.json` |
| evaluate | blocked: no test predictions | `reports/test_metrics.json` / `.csv` |

Training (`scripts/training/train_multitask.py`) includes deterministic seeds, CPU/CUDA support, optional `--amp` mixed precision, focal loss with a positive-class weight derived from the actual training-label imbalance, early stopping (`--patience`), checkpointing to `models/checkpoints/best.pt`, and validation loss/Brier metrics per epoch. A smoke test may only run after `dataset_validation.json` reports no critical failures; it must never be reported as a trained or evaluated model.

Historical replay:

```powershell
python scripts/inference/historical_replay.py 20230701_0015
```

fails clearly unless a trained checkpoint, calibration parameters, and observed (confirmed) spatial labels all exist. None exist today.

## Required additional data

1. INSAT-3DR L1C granules for at least 3+ independent dates covering real thunderstorm, cloudburst, and flood episodes, each with a full 30-minute sequence usable for +2h..+6h horizons.
2. Contemporaneous INSAT QPE (HEM) for those same dates so 1h/3h/6h accumulations can be computed from actual timestamps.
3. IMDAA pressure-level profiles (temperature, humidity, pressure, u/v wind) for the same dates to derive IWV, CAPE, CIN, shear, and convergence.
4. At least one authoritative thunderstorm/lightning observation source (e.g., lightning detection network or IMD storm reports) for confirmed thunderstorm labels.
5. An authoritative cloudburst definition/threshold plus observed rainfall reports for label confirmation.
6. Official flood/inundation observations (gauge exceedance, flood extent, or disaster management reports) for flash-flood labels.
7. Optional: INSAT CMV products for atmospheric motion features.

After adding data, rerun: audit, extract, features, align, labels, validate, sequence, normalize, train, calibrate, thresholds, evaluate. All reports are regenerated deterministically by their stage scripts.