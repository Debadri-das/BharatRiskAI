# BharatRiskAI First-Party File Inventory

This inventory excludes `frontend/node_modules`, generated build output, logs, downloaded HDF5/NetCDF data, model binaries, and notebook cell internals. Paths are relative to the repository root.

## Application entry points

| Path | Responsibility |
|---|---|
| [`backend/main.py`](../backend/main.py) | FastAPI application, middleware, startup validation, route registration |
| [`worker/worker.py`](../worker/worker.py) | Periodic worker loop |
| [`frontend/src/main.jsx`](../frontend/src/main.jsx) | React/Vite browser entry |
| [`scripts/run_pipeline.py`](../scripts/run_pipeline.py) | Offline data pipeline command entry |
| [`ml/training/train.py`](../ml/training/train.py) | Baseline/model training entry |

## Backend

| Directory | Files |
|---|---|
| `backend/api` | `__init__.py`, `dashboard.py`, `emergencies.py`, `health.py`, `nowcast.py`, `recommendations.py`, `reports.py`, `satellite.py`, `zones.py` |
| `backend/services` | `__init__.py`, `alert_delivery.py`, `emergency_service.py`, `geospatial_service.py`, `nowcast_service.py`, `recommendation_service.py`, `report_service.py`, `risk_service.py`, `state_service.py` |
| `backend/schemas` | `__init__.py`, `common.py`, `emergency.py`, `nowcast.py`, `recommendation.py`, `report.py`, `risk.py` |
| `backend/database` | `__init__.py`, `connection.py`, `crud.py`, `local_db.py` |
| `backend/config` | `__init__.py`, `logging.py`, `settings.py` |
| `backend/middleware` | `__init__.py`, `exposure_lock.py`, `rate_limit.py`, `request_id.py` |
| `backend/utils` | `__init__.py`, `geo.py`, `security.py` |
| `backend` | `__init__.py`, `main.py` |

Routes observed in [`backend/api/`](../backend/api/):

- Health/status: `/health`, `/status`
- Dashboard/connectivity: `/dashboard`, `/connectivity`
- Zones/risk: `/zones`, `/risk`, `/risk/{zone_id}`
- Nowcast: `/nowcast/city`, `/nowcast/zone/{zone_id}`, `/nowcast/zone/{zone_id}/xai`, `/nowcast/alerts`
- Reports: `/report`, `/reports`
- Emergencies: `/emergency`, `/emergencies`, `/emergency/{emergency_id}/assign`
- Recommendations: `/recommendations`, `/resources`
- Satellite: `/satellite/status`, `/satellite/latest/{zone_id}`, `/satellite/download/{zone_id}`, `/satellite/process/{zone_id}`

## Ingestion and data processing

| Directory | Files |
|---|---|
| `ingestion` | `__init__.py`, `weather.py`, `satellite_feeds.py`, `satellite.py`, `real_data.py`, `qpe.py`, `population.py`, `pipeline.py`, `insat.py`, `imdaa.py`, `flood_history.py`, `elevation.py`, `drainage.py`, `dem.py` |
| `ml/preprocessing` | `__init__.py`, `clean.py`, `features.py`, `validation.py` |
| `ml/ingestion` | `live_loop.py` |
| `scripts` | `__init__.py`, `align_data.py`, `audit_dataset.py`, `extract_ir_kolkata.py`, `extract_qpe_kolkata.py`, `extract_wv_kolkata.py`, `run_pipeline.py`, `scale_dataset.py`, `transform_and_label.py` |
| `scripts/features` | `__init__.py`, `build_unified_features.py`, `dem_features.py`, `imdaa_features.py`, `qpe_features.py`, `satellite_features.py` |
| `scripts/labels` | `__init__.py`, `build_labels.py`, `contracts.py` |
| `scripts/datasets` | `__init__.py`, `build_sequences.py` |
| `scripts/preprocessing` | `align_datasets.py` |
| `scripts/insat` | `__init__.py`, `extract_l1c.py` |
| `scripts/validation` | `__init__.py`, `validate_dataset.py` |
| `scripts/calibration` | `calibrate.py`, `select_thresholds.py` |
| `scripts/training` | `fit_normalization.py`, `train_multitask.py` |
| `scripts/evaluation` | `evaluate.py` |
| `scripts/inference` | `historical_replay.py` |

## ML and reports

- `ml/nowcasting`: `architecture.py`, `features.py`, `inference.py`, `model.py`
- `ml/models`: `__init__.py`, `baseline.py`, `model_loader.py`, `random_forest.py`
- `ml/training`: `__init__.py`, `train.py`, `metrics.py`, `evaluate.py`
- `reports`: `__init__.py`, `checkpoint_contract.py`, `source_manifest.py`, `unified_feature_schema.py`
- `reports` also contains generated audit, calibration, readiness, threshold, and metric artifacts.

## Worker

| Path | Responsibility |
|---|---|
| `worker/tasks/weather_sync.py` | Invoke latest ingestion for weather |
| `worker/tasks/satellite_sync.py` | Invoke latest ingestion for satellite |
| `worker/tasks/risk_update.py` | Validate supplied nowcast outputs |
| `worker/tasks/report_processing.py` | Process reports |
| `worker/tasks/alert_processing.py` | Process and deliver alerts |
| `worker/worker.py` | Execute task sequence on an interval |

## Frontend

- Pages: `Dashboard.jsx`, `EmergencyCenter.jsx`, `ProjectDetails.jsx`, `Reports.jsx`, `RiskAnalysis.jsx`, `Settings.jsx`
- Layout/common components: `components/layout/*`, `components/common/*`
- Domain components: `components/map/*`, `components/nowcast/*`, `components/risk/*`, `components/reports/*`, `components/emergency/*`, `components/recommendation/*`, `components/mesh/*`
- API clients: `services/api.js`, `emergencyApi.js`, `nowcastApi.js`, `recommendationApi.js`, `reportApi.js`, `riskApi.js`, `demoData.js`
- Stores: `store/emergencyStore.js`, `notificationStore.js`, `preferencesStore.js`, `riskStore.js`, `uiStore.js`
- Offline: `offline/indexedDB.js`, `offline/offlineQueue.js`, `offline/serviceWorker.js`, `offline/syncManager.js`
- Utilities: `utils/format.js`, `utils/geo.js`, `utils/network.js`, `utils/validation.js`
- Entry/config/tests: `App.jsx`, `App.test.jsx`, `main.jsx`, `index.html`, `vite.config.js`, `package.json`, `package-lock.json`

## Database, configuration, docs, and deployment

- Database: `database/init.sql`, `database/seed.py`, `supabase_schema.sql`
- Configuration: `config/alerts.yaml`, `calibration.yaml`, `data.yaml`, `labels.yaml`, `model.yaml`, `source_manifest.json`, `training.yaml`, `.env.example`
- Deployment: `docker-compose.yml`, `infra/Dockerfile.backend`, `infra/Dockerfile.frontend`, `infra/Dockerfile.worker`, `infra/nginx.conf`
- Documentation: `README.md`, `README_DATA_PIPELINE.md`, `docs/api.md`, `docs/architecture.md`, `docs/deployment.md`, `docs/ml-model.md`
- Top-level utilities/tests: `create_flood_mask.py`, `create_thunderstorm_labels.py`, `extract_labels.py`, `final_verification.py`, `format_labels.py`, `merge_dem.py`, `process_remal.py`, `process_yaas.py`, `test_connection.py`, `test_db_connection.py`, `test_nowcast.py`, `test_supabase_url.py`, `log_config.json`, `Makefile`

## External dependencies

- Python dependencies are pinned in [`requirements.txt`](../requirements.txt), including FastAPI/Uvicorn, Pydantic, Supabase, NumPy/Pandas/scikit-learn, rasterio/xarray/HDF5/NetCDF tooling, PyTorch, pytest, httpx, and websockets.
- Frontend dependencies are declared in [`frontend/package.json`](../frontend/package.json), including React, Vite, React Leaflet, Recharts, Zustand, Vitest, jsdom, Testing Library, and Lucide.
- External services/configuration observed in source: Supabase, Copernicus Data Space, MOSDAC/IMDAA, SMTP, alert webhooks, and local filesystem data/model artifacts.
