# BharatRisk AI

BharatRisk AI — local, open-source disaster intelligence prototype (hackathon-ready MVP).

Quick start (dev):

1. Create a Python virtualenv and install backend deps:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
pip install -r requirements.txt
```

2. Initialize DB and seed demo data:

```bash
python database/seed.py
```

3. (Optional) Train ML model:

```bash
python -m ml.training.train
```

4. Start backend:

```bash
make backend
```

5. Frontend (in a separate terminal):

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173

Notes:
- The backend runs at http://localhost:8000 by default.
- Demo data is seeded for a Kolkata scenario.
- If no ML model artifact exists, the backend falls back to the heuristic predictor.
# BharatRisk AI

BharatRisk AI is a hackathon-ready disaster intelligence prototype for flood-risk prediction, what-if simulation, authority recommendations, citizen ground intelligence, offline-first reporting, and an Android mesh-SOS concept.

Core statement:

> BharatRisk AI doesn't just predict where flooding may happen. It simulates what could happen next, recommends what authorities should do, incorporates citizen ground intelligence, and keeps emergency communication alive when connectivity fails.

## Architecture

- Frontend: React, Vite, Leaflet, Recharts, Zustand, Service Worker, IndexedDB.
- Backend: FastAPI, Pydantic, SQLAlchemy, SQLite.
- ML: pandas, numpy, scikit-learn Random Forest, joblib, with deterministic synthetic demo fallback.
- Mobile mesh: Android Kotlin prototype with packet validation, TTL, duplicate detection, hop count, local queue, and gateway flow.
- Demo mode: deterministic Kolkata extreme-rainfall scenario, no paid APIs or API keys.

## Features

- Interactive Kolkata flood-risk map with LOW, MEDIUM, HIGH, and CRITICAL zones.
- Zone detail showing rainfall, elevation, drainage, exposed population, flood history, citizen reports, and risk contribution breakdown.
- Local risk engine and trainable Random Forest model.
- What-if simulator using the trained/current model without retraining on slider movement.
- Ranked resource recommendations with reasons.
- Citizen report submission that associates reports with the nearest zone and recalculates risk.
- Emergency SOS flow with priority calculation and mesh route simulator.
- Offline cached dashboard, queued reports, queued SOS messages, and later sync.

## Installation

Backend:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python database/seed.py
```

Frontend:

```bash
cd frontend
npm install
```

## Running

Backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

## Training ML Model

```bash
python -m ml.training.train
```

If no real dataset exists, training creates `ml/datasets/processed/flood_demo_training.csv` from deterministic synthetic data and saves `ml/artifacts/flood_risk_model.pkl`. The synthetic dataset is only for demonstration and can be replaced with verified rainfall, elevation, drainage, population, flood history, and citizen report datasets.

## Demo Flow

1. Open BharatRisk AI.
2. Show the flood-risk map and select `Zone 17 - Dhapa Wetlands`.
3. Show risk breakdown.
4. Open What-If Simulator.
5. Increase rainfall by 30 percent and reduce drainage by 40 percent.
6. Run simulation and show higher risk, newly affected population, and recommendations.
7. Submit a citizen flood report.
8. Use Settings to simulate internet failure.
9. Open Emergency Center and send demo SOS.
10. Show PHONE A -> PHONE B -> PHONE C -> GATEWAY route.
11. Restore internet and synchronize queued information.

## API

Base URL: `http://localhost:8000/api`

- `GET /health`
- `GET /dashboard`
- `GET /zones`
- `GET /risk`
- `GET /risk/{zone_id}`
- `POST /simulation`
- `POST /report`
- `GET /reports`
- `POST /emergency`
- `GET /emergencies`
- `POST /emergency/{id}/assign`
- `GET /recommendations`
- `GET /resources`
- `GET /connectivity`

## Android Mesh Prototype

Open `mesh-android/` in Android Studio and run the app. The prototype models packet creation, signing, duplicate suppression, TTL expiry, hop counting, persistence, and gateway upload. The current repo includes a deterministic simulator so the demo can show A -> B -> C -> Gateway without requiring multiple physical devices.

## Security

The project implements practical prototype security: environment-based token configuration, CORS, rate limiting, request IDs, input validation, packet IDs, timestamps, TTL, duplicate detection, and basic packet signing. It does not claim military-grade security.

## Offline Architecture

The browser app uses a service worker for cached shell/dashboard access and IndexedDB for queued reports and emergencies. A normal browser is not presented as an arbitrary multi-hop Bluetooth mesh device; nearby-device mesh behavior belongs to the Android prototype and bridge.

## Limitations

- Demo data is deterministic and synthetic.
- Live weather, satellite, elevation, drainage, and population providers are adapter stubs with local fallbacks.
- Android nearby-device transport is a prototype/simulator in this environment.
- SQLite is used for local deployment; the model layer is structured so PostgreSQL/PostGIS can be added later.

## Future Improvements

- Replace synthetic data with vetted IMD, DEM, drainage, population, and historical flood datasets.
- Add PostGIS geometry and polygon rendering.
- Implement production BLE/Wi-Fi Direct transport and interoperability tests.
- Add authority authentication and role-scoped dashboards.
