# SkyGuard: Space-Powered Hyper-Local Early Warning System

**SkyGuard** is an AI-driven hyper-local early warning system for severe weather conditions that leverages **satellite data, geospatial analysis, and real-time ML models** to provide minute-level predictions for natural disasters.

## 🛰️ Mission Statement

> SkyGuard doesn't just predict weather. It ingests live satellite imagery and meteorological data from space platforms, analyzes hyper-local geospatial conditions using ML models, and delivers **real-time early warnings down to the street level** — before severe weather strikes.

**Theme**: Space Technology  
**Problem Statement**: AI-driven hyper-local early warning system for severe weather  

---

## 🌍 How It Works: Satellite-to-Device

1. **Satellite Data Ingestion** → Real-time satellite imagery and weather data from NOAA, Sentinel, and meteorological APIs
2. **Geospatial ML Analysis** → AI models analyze hyper-local terrain, elevation, drainage, urban heat, and population density
3. **Minute-Level Predictions** → Rainfall, heatwaves, flooding, cyclones, and landslide risk at pincode/district level
4. **Multi-Channel Alerts** → Push notifications, mesh-based emergency broadcast, offline messaging
5. **Authority Dashboard** → Real-time resource deployment recommendations

---

## 🏗️ Architecture

- **Frontend**: React + Vite + Leaflet (interactive satellite map) + Recharts (risk analytics) + Service Worker (offline capability)
- **Backend**: FastAPI + SQLAlchemy + PostGIS (geospatial queries)
- **Satellite Data Pipeline**: 
  - Ingestion: NOAA GFS, Sentinel-2 SAR, weather APIs
  - Processing: Cloud detection, vegetation indices (NDVI), rainfall accumulation
  - ML Models: TensorFlow/scikit-learn for rainfall/flood/cyclone forecasting
- **Mobile Mesh**: Android Kotlin + Bluetooth/Wi-Fi Direct for device-to-device emergency routing
- **Demo Mode**: Deterministic extreme weather scenarios with satellite imagery simulation

---

## ⚡ Core Features

### 1. **Satellite Risk Map**
- Real-time satellite imagery overlays
- AI-computed risk zones (LOW, MEDIUM, HIGH, CRITICAL) at hyperlocal resolution
- Temperature heatmaps, rainfall prediction layers, flood inundation modeling
- Population exposure analysis overlaid on satellite data

### 2. **Early Warning Engine**
- **Real-Time Satellite Processing**: Ingests NOAA, Sentinel-2, and meteorological data
- **Minute-Level Forecasts**: Rainfall predictions 4-6 hours in advance
- **Geospatial ML Models**: Trained on historical satellite imagery + ground truth
- **Confidence Scoring**: Probabilistic forecasts with uncertainty quantification

### 3. **What-If Simulator**
- Simulate monsoon intensification, cloud movement, urban heat island effects
- Test alert thresholds and response strategies
- Export scenario reports for authority planning

### 4. **Authority Dashboard**
- Resource deployment recommendations with satellite-validated impact zones
- Real-time SOS routing and mesh-based emergency coordination
- Historical flood/disaster patterns from satellite archives

### 5. **Offline-First Citizen App**
- Cached satellite tiles and risk layers (service worker)
- Queued citizen ground reports (validated against satellite data)
- Emergency SOS with multi-hop mesh routing
- Auto-sync when internet returns

### 6. **Mesh Emergency Network**
- Device-to-device mesh for areas with no connectivity
- Packet signing and multi-hop relay
- Automatic gateway upload to authority systems

---

## 📦 Quick Start

### Backend Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

<<<<<<< HEAD
2. Configure Supabase:

Create `.env` in the repository root from `.env.example`, then set the Project URL and backend API key from **Supabase → Project Settings → API**. Keep `.env` private. In the Supabase SQL Editor, run [`supabase_schema.sql`](supabase_schema.sql).

```env
ENVIRONMENT=development
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-backend-only-key
SUPABASE_SERVICE_ROLE_KEY=your-server-only-service-role-key
API_TOKEN=replace-with-a-long-random-token
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

`SUPABASE_KEY` is used by the application. `SUPABASE_SERVICE_ROLE_KEY` is used only by trusted maintenance commands such as `database/seed.py`; never expose it to the frontend.

3. Initialize Supabase tables and seed demo zones:

```bash
=======
# Initialize database with satellite metadata
>>>>>>> ba8745a0a07e09770a962fd06cbda76f200d36e6
python database/seed.py

# Train satellite-based ML models
python -m ml.training.train_satellite_models
```

<<<<<<< HEAD
4. Verify the connection:

```text
http://localhost:8000/api/health
```

The health response should report `status: ok`, `database.reachable: true`, and a non-zero `zone_count`.

5. (Optional) Train ML model:

=======
### Frontend Setup
>>>>>>> ba8745a0a07e09770a962fd06cbda76f200d36e6
```bash
cd frontend
npm install
npm run dev
# Open: http://localhost:5173
```

<<<<<<< HEAD
6. Start backend:

=======
### Start Backend
>>>>>>> ba8745a0a07e09770a962fd06cbda76f200d36e6
```bash
make backend
# Runs at: http://localhost:8000
```

<<<<<<< HEAD
7. Frontend (in a separate terminal):
=======
---

## 🛰️ Satellite Data Integration

### Data Sources
- **NOAA GFS**: Global weather forecast model (0.25° resolution)
- **Sentinel-2**: ESA multispectral imagery for vegetation & flood detection
- **SAR (Sentinel-1)**: Synthetic Aperture Radar for cloud-pierce rainfall detection
- **Elevation & Drainage**: SRTM DEM + OpenStreetMap hydrology
- **Population**: LandScan or Facebook M4D data

### ML Pipeline
```
Satellite Image → Cloud Mask → NDVI/MNDWI/Indices → 
  Rainfall Accumulation + Terrain Slope + Drainage Network + Urban Cover → 
    Random Forest / TensorFlow Model → 
      Flood/Landslide/Cyclone Risk Score
```

### Processing
- Ingestion: `ingestion/satellite_pipeline.py` — fetches, tiles, and caches imagery
- Features: `ml/features/geospatial.py` — computes ML-ready indicators
- Training: `ml/training/train_satellite_models.py` — cross-validates on historical disasters
- Inference: Backend API runs live predictions every 15 minutes

---

## 🎯 Demo Flow (Satellite Theme)

1. **Open SkyGuard Dashboard** → See live satellite map with thermal/rainfall overlays
2. **Select High-Risk Zone** → View satellite-derived risk breakdown
3. **What-If: Monsoon Intensification** → Simulate increased rainfall from satellite feed
4. **Authority Dashboard** → See resource recommendations validated by satellite data
5. **Emergency Scenario** → Citizen reports auto-validated against satellite observations
6. **Offline Mode** → Cached satellite tiles and queued alerts sync when online
7. **Mesh Routing** → Multi-hop SOS relay to gateway

---

## 📡 API Reference

**Base URL**: `http://localhost:8000/api`

```
GET    /health                           # System status
GET    /dashboard                        # Real-time satellite risk snapshot
GET    /satellite/latest                 # Latest satellite imagery tile
GET    /zones                            # Hyperlocal risk zones
GET    /risk/{zone_id}                   # Satellite-validated risk details
GET    /forecast/{zone_id}               # 4-6 hour ML forecast
POST   /simulation                       # What-if satellite scenario
POST   /report                           # Citizen report + satellite validation
GET    /reports                          # List validated reports
POST   /emergency                        # SOS with mesh routing
GET    /emergencies                      # List active emergencies
POST   /emergency/{id}/assign            # Authority resource assignment
GET    /recommendations                  # Satellite-validated resource recommendations
GET    /resources                        # Available authority resources
GET    /connectivity                     # Mesh network status
```

---

## 📱 Android Mesh (Emergency Broadcast)

**Location**: `mesh-android/`
>>>>>>> ba8745a0a07e09770a962fd06cbda76f200d36e6

```bash
# Compile and run JVM test harness (no Android hardware needed)
cd mesh-android
kotlinc -cp "$(pwd)" -d mesh.jar app/src/main/java/com/bharatrisk/mesh/*.kt
kotlin -cp mesh.jar com.bharatrisk.mesh.TestHarnessKt
```

Features:
- Multi-hop packet relay (A → B → C → Gateway)
- Packet deduplication and TTL expiry
- Signed messages (HMAC-based)
- Local persistence & queuing
- Automatic gateway upload when online

---

## 🔒 Security

- **Satellite Data**: HTTPS-only, rate-limited API clients
- **Device Mesh**: HMAC packet signing, TTL validation, duplicate detection
- **User Data**: Environment-based tokens, CORS, input validation
- **Alerts**: TLS for emergency broadcasts

---

## 📊 Deployment

### Docker Compose
```bash
docker-compose up -d
```

### Cloud Deployment
- **Backend**: FastAPI → AWS ECS / Google Cloud Run
- **Database**: PostgreSQL + PostGIS for geospatial queries
- **Satellite Pipeline**: Scheduled Lambda/Cloud Functions (every 15 min)
- **Frontend**: CDN (CloudFront / Cloud CDN)

---

## 🚧 Limitations & Future Work

### Current
- Synthetic satellite data for MVP (demo Kolkata scenario)
- Simulator for mesh transport (use Android APIs for BLE/Wi-Fi Direct in production)
- SQLite for local storage (production uses PostgreSQL + PostGIS)

### Next Steps
- Integrate live NOAA, Sentinel-2, and SAR feeds with proper authentication
- Add PostGIS vector geometry for polygon-based flood modeling
- Deploy machine learning on GPU (TensorFlow Lite for mobile inference)
- Authority authentication & role-based dashboards
- Multi-language support (Hindi, Tamil, Bengali, Marathi, etc.)
- Historical satellite archive search for disaster retrospectives
- Integration with national disaster management systems (NDMA, IMD)

---

## 🌐 Use Cases

✅ **Monsoon Forecasting** — Early warnings 4-6 hours before intense rainfall  
✅ **Urban Flooding** — Street-level inundation predictions for cities  
✅ **Cyclone Tracking** — Real-time satellite-guided evacuation routing  
✅ **Landslide Risk** — Slope stability assessment using SAR and DEM  
✅ **Heatwave Alerts** — Thermal anomaly detection for vulnerable populations  
✅ **Connectivity Gaps** — Mesh-based alerts for remote areas with no network  

---

## 📝 License

Other (open-source; see LICENSE)

<<<<<<< HEAD
## Real Data Ingestion

The ingestion boundary accepts downloaded provider files and does not silently substitute demo values:

- IMDAA: NetCDF/NetCDF4 with specific humidity, pressure levels, temperature, and U/V wind variables.
- INSAT-3D/3DR: NetCDF or HDF5 with water-vapor, calibrated thermal-infrared, and optional QPE variables.
- DEM: GeoTIFF from SRTM, CartoDEM, or another licensed elevation source.

Create these directories and place the newest files in each:

```text
data/imdaa/
data/insat/
data/dem/
```

Configure variable names in the adapter call when the provider product uses names other than the defaults in `ingestion/real_data.py`. Run the continuous worker with:

```bash
.venv\\Scripts\\python.exe worker\\worker.py
```

The worker records grids in `grid_observations`, run health in `ingestion_runs`, and derives IWV in kg/m2, CTT in Celsius, and DEM slope in degrees.

### Manual provider steps

1. Request IMDAA access from the authorized NCMRWF/India data portal and download a small NetCDF sample for the target region.
2. Request MOSDAC access and confirm the INSAT-3D/3DR WV, TIR, and QPE product formats and calibration metadata.
3. Download SRTM or CartoDEM GeoTIFF coverage for the monitored region and confirm its CRS/resolution.
4. Place files in the configured directories and run `python worker/worker.py` once to validate ingestion.
5. Configure `ALERT_WEBHOOK_URL` or `ALERT_SMS_WEBHOOK_URL` with the responder gateway endpoint. The delivery code records every attempt in `alert_deliveries`.
## Demo Flow
=======
---
>>>>>>> ba8745a0a07e09770a962fd06cbda76f200d36e6

**Built for India's resilience. Powered by satellite data. Protected by AI.**
