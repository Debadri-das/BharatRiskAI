# BharatRiskAI

## Space-Powered Hyper-Local Severe Weather Early Warning System

BharatRiskAI is an AI-driven early warning platform designed to detect and forecast severe weather hazards in India using **satellite observations, atmospheric data, rainfall estimates, terrain information, and spatiotemporal machine learning**.

The system focuses on probabilistic forecasting of:

- ⛈️ Thunderstorms
- 🌧️ Cloudbursts / extreme rainfall events
- 🌊 Flash-flood risk

The core forecasting system is designed to provide **2–6 hour probabilistic hazard forecasts** on a common approximately **5 km spatial grid**, while the application layer provides visualization, alerts, citizen reporting, authority tools, and offline emergency communication.

---

# 🎯 Project Objective

Severe weather events can develop rapidly and affect relatively small geographic regions.

BharatRiskAI combines multiple sources of information to understand both:

1. **What is happening in the atmosphere now**
2. **How those conditions are changing**
3. **Where the event is likely to develop**
4. **Which areas may subsequently experience hazardous rainfall or flooding**

The system follows the pipeline:

```text
Satellite + Atmospheric + Rainfall + Terrain Data
                        ↓
               Data Quality Control
                        ↓
              Feature Engineering
                        ↓
           Spatial + Temporal Alignment
                        ↓
             Historical Sequences
                        ↓
          Spatiotemporal ML Model
                        ↓
       ┌────────────────┼────────────────┐
       ↓                ↓                ↓
 Thunderstorm       Cloudburst       Flash Flood
 Probability       Probability       Probability
       └────────────────┼────────────────┘
                        ↓
               Calibration & Thresholds
                        ↓
              Risk & Alert Generation
                        ↓
          Dashboard / Authority / Citizen
```

---

# 🛰️ Data Sources

BharatRiskAI is designed around the following scientific data sources.

## 1. INSAT-3DR

INSAT-3DR provides the primary satellite observations used for monitoring cloud and atmospheric conditions.

Important channels/products include:

| Data | Purpose |
|---|---|
| TIR1 | Cloud-top thermal characteristics |
| TIR2 | Additional thermal characterization |
| WV | Water-vapour-sensitive atmospheric information |
| VIS | Cloud structure during daylight |
| SWIR | Cloud/surface characterization |
| MIR | Additional cloud and thermal characterization |
| QPE | Quantitative precipitation estimation |

The current pipeline works with INSAT-3DR Level-1C observations and QPE products obtained through MOSDAC.

---

## 2. IMDAA

IMDAA atmospheric data provides meteorological information that satellite imagery alone cannot directly provide.

The intended variables include:

- Temperature
- Specific humidity
- Pressure
- U-wind
- V-wind
- Pressure-level atmospheric profiles

These are used to derive or calculate meteorological features such as:

- Integrated Water Vapour (IWV)
- CAPE
- CIN
- Wind shear
- Horizontal convergence

---

## 3. DEM

A Digital Elevation Model provides terrain information.

BharatRiskAI uses:

- Elevation
- Slope

Terrain information is particularly important for understanding spatial differences in flood susceptibility and water accumulation.

---

## 4. Hazard Observations

Historical hazard observations are required to create reliable training labels.

Potential sources include:

- Authoritative thunderstorm/lightning observations
- Official extreme-rainfall/cloudburst observations
- Flood and inundation observations
- Other verified event records

These observations are kept separate from satellite-derived proxy indicators.

---

# 🧠 Machine Learning Architecture

BharatRiskAI uses a **multitask spatiotemporal forecasting architecture**.

Instead of predicting each hazard completely independently, the model learns a shared representation of the atmospheric and geographical state.

```text
                  Historical Multimodal Data
                           │
                           ▼
              Shared Spatiotemporal Backbone
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
       Thunderstorm    Cloudburst    Flash Flood
          Head            Head           Head
             │             │             │
             ▼             ▼             ▼
       Probability     Probability    Probability
           Map             Map            Map
```

## Input Data

A model sample contains a sequence of observations over time.

Each spatial grid cell can contain features such as:

```text
INSAT:
    TIR1
    TIR2
    WV
    VIS
    SWIR
    MIR

Rainfall:
    QPE
    1-hour accumulation
    3-hour accumulation
    6-hour accumulation

Atmospheric:
    Temperature
    Humidity
    Pressure
    U wind
    V wind
    IWV
    CAPE
    CIN
    Wind shear
    Convergence

Terrain:
    Elevation
    Slope
```

---

# ⏱️ Temporal Forecasting

Weather is dynamic, so the model does not rely only on the latest satellite image.

It uses a historical sequence such as:

```text
T-2h
T-1.5h
T-1h
T-30m
T
```

and predicts future hazard probabilities for:

```text
T+2h
T+3h
T+4h
T+5h
T+6h
```

The exact sequence length can be configured according to the available training dataset.

This allows the model to learn temporal patterns such as:

- Cloud-top cooling
- Cloud development
- Rainfall intensification
- Moisture evolution
- Wind evolution
- Atmospheric instability
- Spatial propagation of weather systems

---

# 🔬 Feature Engineering

Raw observations are converted into physically meaningful features before being supplied to the ML model.

## Cloud-Top Temperature

Thermal infrared observations are calibrated and used to derive cloud-top temperature information.

```text
TIR observations
       ↓
Calibration
       ↓
Cloud-top temperature
       ↓
Spatial / temporal evolution
```

---

## Cloud-Top Cooling

Cloud-top temperature change can be calculated over time.

For example:

```text
Cooling Rate =
CTT(t) - CTT(t-Δt)
-------------------
       Δt
```

Rapid cloud-top cooling can act as a proxy indicator of developing deep convection.

---

## Rainfall Accumulation

QPE observations are accumulated over different periods:

```text
1-hour rainfall
3-hour rainfall
6-hour rainfall
```

These features help the model understand both recent rainfall intensity and accumulated rainfall loading.

---

## Integrated Water Vapour

When valid atmospheric profiles are available:

```text
Humidity Profile
       ↓
Vertical Integration
       ↓
Integrated Water Vapour
```

IWV is used as an atmospheric moisture feature.

---

## CAPE

CAPE is derived from atmospheric thermodynamic information and represents convective energy available in the atmosphere.

It is used as a **model feature**, not as a thunderstorm label.

---

## CIN

CIN represents convective inhibition and provides information about the atmospheric barrier to convection.

---

## Wind Shear

U/V wind information at different atmospheric levels is used to estimate vertical wind shear.

---

## Convergence

Horizontal wind fields can be used to estimate areas of atmospheric convergence.

---

## Terrain Features

DEM data provides:

```text
Elevation
    ↓
Terrain gradient
    ↓
Slope
```

These features provide geographical context for flood-related prediction.

---

# 🗺️ Spatial and Temporal Alignment

The input datasets have different:

- Spatial resolutions
- Coordinate systems
- Grid structures
- Temporal frequencies

Therefore, BharatRiskAI aligns valid observations onto a common machine-learning grid.

Current ML configuration:

```text
Coordinate system : EPSG:4326
Grid resolution   : approximately 0.05°
Spatial size      : approximately 114 × 84 cells
Temporal interval : 30 minutes
```

The project does not treat missing observations as valid measurements.

Unknown observations remain unknown instead of being silently converted into negative labels.

---

# 🏷️ Labeling Strategy

BharatRiskAI uses a **tri-state labeling system**:

```text
1      = Hazard observed
0      = Hazard not observed
null   = Unknown / insufficient evidence
```

Each label also stores provenance information such as:

- Hazard type
- Label type
- Source
- Timestamp
- Threshold
- Accumulation window
- Spatial rule
- Confidence
- Provenance

## Confirmed vs Proxy Labels

The system distinguishes between:

### Confirmed labels

Labels supported by authoritative observations.

```text
Actual thunderstorm observation
Actual cloudburst observation
Actual flood observation
```

### Proxy labels

Indicators derived from satellite or meteorological variables.

Example:

```text
Very cold cloud top
+
Rapid cloud-top cooling
        ↓
Thunderstorm proxy
```

A proxy is **not treated as confirmed ground truth**.

---

# ⚠️ Important Scientific Distinctions

BharatRiskAI deliberately avoids several common data-science mistakes.

### QPE ≠ Flood Ground Truth

Heavy rainfall does not automatically mean flooding.

```text
Heavy Rainfall
      ≠
Flash Flood
```

QPE is therefore used primarily as an input/feature and can contribute to proxy labeling where appropriate.

---

### CAPE ≠ Thunderstorm Label

CAPE indicates atmospheric instability.

It is a predictive feature, not proof that a thunderstorm occurred.

---

### Satellite Proxy ≠ Confirmed Event

A satellite signal may indicate conditions associated with a hazard, but authoritative observations are preferred for final ground truth.

---

# 🧪 Training Pipeline

The training workflow is:

```text
Raw Data
   ↓
Audit
   ↓
INSAT Extraction
   ↓
IMDAA Processing
   ↓
QPE Processing
   ↓
DEM Processing
   ↓
Spatial Alignment
   ↓
Feature Engineering
   ↓
Label Generation
   ↓
Sequence Construction
   ↓
Train / Validation / Test Split
   ↓
Normalization
   ↓
Model Training
   ↓
Calibration
   ↓
Threshold Selection
   ↓
Final Evaluation
```

---

# 🔐 Data Leakage Prevention

The pipeline is designed to prevent temporal leakage.

Training, validation and test data are separated by **event/date groups**, rather than randomly splitting individual satellite frames.

This prevents nearly identical consecutive weather frames from appearing in both training and testing datasets.

Normalization statistics are calculated from the training set only.

Calibration is performed using validation predictions only.

The final test set remains untouched until evaluation.

---

# 📊 Model Evaluation

The system is intended to evaluate probabilistic hazard forecasts using metrics such as:

### Classification metrics

- Precision
- Recall
- F1-score
- PR-AUC
- CSI
- POD
- FAR
- IoU / Dice

### Probabilistic metrics

- Brier Score
- Expected Calibration Error (ECE)
- Reliability diagrams

Metrics are evaluated separately for different hazards and forecast lead times.

---

# 📈 Probability Calibration

Raw neural-network probabilities are not automatically guaranteed to be well calibrated.

Therefore:

```text
Model prediction
       ↓
Validation predictions
       ↓
Temperature scaling
       ↓
Calibrated probability
```

Thresholds are also selected using validation data rather than the test set.

---

# 🗄️ Database Architecture

The application layer uses a backend database for operational information.

Conceptually:

```text
Processed Scientific Data
          ↓
    Observation Grid
          ↓
      Database
          ↓
    FastAPI Backend
          ↓
   React Application
```

The database can contain information such as:

- Geographic zones
- Processed grid observations
- Forecast records
- Risk information
- Citizen reports
- Emergency/SOS records
- Authority resources
- Alert delivery records
- Ingestion status

Large raw satellite files such as HDF5/NetCDF files are kept in the data storage pipeline rather than being stored as individual database rows.

---

# ⚙️ Backend

The backend is built around **FastAPI**.

Its responsibilities include:

- Serving forecasts
- Serving risk information
- Managing geographic zones
- Receiving citizen reports
- Managing emergencies
- Providing authority resources
- Handling alert delivery
- Connecting application services with processed observations and model predictions

---

# 🖥️ Frontend

The frontend uses:

- React
- Vite
- Leaflet
- Recharts
- Service Worker / offline support

The dashboard is designed to display:

- Satellite-derived layers
- Hazard probability maps
- Risk zones
- Forecast information
- Historical observations
- Emergency information
- Authority resource information

---

# 📱 Offline and Emergency Communication

BharatRiskAI includes an offline-first application layer.

When normal internet connectivity is unavailable:

```text
Citizen Device
      ↓
Offline Storage
      ↓
Bluetooth / Wi-Fi Direct
      ↓
Nearby Device
      ↓
Multi-Hop Relay
      ↓
Internet-Connected Gateway
      ↓
BharatRiskAI Backend
```

The Android mesh prototype supports:

- Multi-hop packet relay
- Packet deduplication
- TTL expiry
- Signed messages
- Local persistence
- Gateway upload

This layer is designed primarily for **emergency communication**, rather than replacing the scientific forecasting pipeline.

---

# 🚨 Early Warning Flow

A simplified operational flow is:

```text
INSAT / IMDAA / QPE / DEM
            ↓
      Data Processing
            ↓
      Feature Extraction
            ↓
    Spatiotemporal Model
            ↓
   Hazard Probability Maps
            ↓
       Calibration
            ↓
      Risk Assessment
            ↓
    ┌───────┴────────┐
    ↓                ↓
Citizen Alerts   Authority Dashboard
    ↓                ↓
Offline/Mesh     Resource Planning
```

---

# 🔄 Real-Time Data Pipeline

The intended operational pipeline is:

```text
Provider Data
     ↓
Ingestion Worker
     ↓
Quality Control
     ↓
Feature Generation
     ↓
Common Grid
     ↓
Latest Observation
     ↓
Model Inference
     ↓
Hazard Probability
     ↓
Backend API
     ↓
Dashboard / Alerts
```

The ingestion worker records processing status and processed grid observations.

---

# 📁 Project Structure

A simplified project structure is:

```text
BharatRiskAI/
│
├── backend/
│   ├── api/
│   ├── services/
│   ├── database/
│   └── main.py
│
├── frontend/
│   └── src/
│       ├── pages/
│       ├── services/
│       ├── offline/
│       └── mesh/
│
├── ingestion/
│   ├── pipeline.py
│   ├── real_data.py
│   └── weather.py
│
├── training/
│   └── ...
│
├── models/
│   └── checkpoints/
│
├── data/
│   ├── insat/
│   │   ├── l1c/
│   │   │   ├── raw/
│   │   │   └── processed/
│   │   └── qpe/
│   │       ├── raw/
│   │       └── processed/
│   │
│   ├── imdaa/
│   │   ├── raw/
│   │   └── processed/
│   │
│   └── dem/
│
├── mesh-android/
│
├── scripts/
│
├── reports/
│
├── requirements.txt
├── .env.example
└── README.md
```

---

# 🚀 Installation

## 1. Clone the repository

```bash
git clone https://github.com/Anuj-Dutta/BharatRiskAI.git
cd BharatRiskAI
```

---

## 2. Create Python environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Configuration

Create a `.env` file from `.env.example`.

Example:

```env
ENVIRONMENT=development

SUPABASE_URL=your-project-url
SUPABASE_KEY=your-backend-key

API_TOKEN=your-random-api-token

CORS_ORIGINS=http://localhost:5173
```

Never commit:

```text
.env
API keys
Passwords
Service-role keys
Provider credentials
```

to GitHub.

---

# 🛰️ Real Data Setup

The real-data ingestion layer accepts provider datasets.

## INSAT

Place INSAT data under:

```text
data/insat/
```

The pipeline expects the relevant INSAT HDF5/NetCDF products and their calibration metadata.

The current scientific pipeline uses:

- INSAT-3DR L1C
- Thermal infrared information
- Water-vapour information
- QPE where available

---

## IMDAA

Place IMDAA NetCDF/NetCDF4 files under:

```text
data/imdaa/
```

Required atmospheric information may include:

```text
Temperature
Specific humidity
Pressure levels
U wind
V wind
```

---

## DEM

Place the DEM GeoTIFF under:

```text
data/dem/
```

The preprocessing stage derives terrain features such as:

```text
Elevation
Slope
```

---

# 🔍 Data Audit

Before processing data:

```bash
python scripts/run_pipeline.py --stage audit
```

The audit checks:

- Available files
- Timestamps
- Corrupt/truncated files
- Dataset coverage
- Missing sources
- Event/date coverage

The pipeline does not silently convert missing scientific observations into valid measurements.

---

# 🧪 Scientific Training Status

The scientific model should only be trained when sufficient valid data and labels are available.

The pipeline intentionally blocks training when:

- Too many target labels are unknown
- There are insufficient independent event/date groups
- Required datasets are missing
- Confirmed labels are unavailable
- Validation/test datasets cannot be constructed safely

This is intentional.

The system should **not** solve missing labels by converting:

```text
unknown → 0
```

because that would create artificial ground truth.

---

# 📦 Current Dataset Status

The current prototype dataset contains:

- INSAT-3DR L1C observations for an initial historical date
- A limited QPE sample
- Kolkata DEM
- No complete IMDAA overlap yet
- No sufficient authoritative thunderstorm labels
- No sufficient authoritative cloudburst labels
- No confirmed flash-flood labels

Therefore, the full scientific train/validation/test pipeline is not yet considered production-ready.

Additional historical event dates and authoritative hazard observations are required before meaningful supervised evaluation.

---

# ⚠️ Current Limitations

BharatRiskAI is an active research/prototype project.

Current limitations include:

1. Limited historical event coverage
2. Incomplete overlap between INSAT, QPE and IMDAA datasets
3. Insufficient confirmed hazard labels
4. Limited flash-flood ground truth
5. Proxy labels cannot replace authoritative observations
6. The current model should not be considered production-validated
7. Offline mesh functionality requires appropriate Android hardware testing
8. Forecast quality depends strongly on the quality and coverage of historical training events

---

# 🛠️ Development Roadmap

## Phase 1 — Data Foundation

- [x] INSAT-3DR data ingestion
- [x] HDF5 inspection
- [x] Satellite calibration pipeline
- [x] Common spatial grid
- [x] DEM processing
- [ ] Complete IMDAA integration
- [ ] More QPE dates
- [ ] Historical event collection

## Phase 2 — Labeling

- [x] Tri-state label structure
- [x] Label provenance
- [x] Proxy label support
- [ ] Confirmed thunderstorm observations
- [ ] Confirmed cloudburst observations
- [ ] Confirmed flood observations

## Phase 3 — Machine Learning

- [x] Sequence-building framework
- [x] Event/date-based splitting
- [x] Training-only normalization
- [x] Multitask architecture
- [x] Calibration framework
- [ ] Sufficient training dataset
- [ ] Full model training
- [ ] Independent test evaluation

## Phase 4 — Application

- [x] React dashboard
- [x] FastAPI backend
- [x] Geographic risk visualization
- [x] Database integration
- [x] Offline storage
- [x] Android mesh prototype
- [ ] Extended real-world field testing

---

# 🧭 Target Use Cases

BharatRiskAI is primarily designed for severe-weather early warning scenarios such as:

### ⛈️ Severe Thunderstorms

Identify areas showing atmospheric and satellite signatures associated with developing convection.

### 🌧️ Extreme Rainfall / Cloudburst

Combine satellite evolution, QPE, atmospheric moisture and instability to estimate the probability of extreme rainfall.

### 🌊 Flash-Flood Risk

Combine rainfall evolution with terrain and atmospheric conditions to estimate the probability of subsequent flash-flood hazards.

---

# 🔬 Research Principles

BharatRiskAI follows several principles:

### No fabricated ground truth

Unknown observations remain unknown.

### No random temporal splitting

Weather sequences are split by independent dates/events to reduce temporal leakage.

### No test-set calibration

Calibration and threshold selection use validation data.

### No feature-label confusion

Meteorological variables such as CAPE, CTT and QPE are not automatically treated as hazard ground truth.

### Full provenance

Labels and observations should retain information about their source and processing history.

---

# 🔒 Security

The system should:

- Keep credentials in environment variables
- Never expose backend service keys to the frontend
- Use HTTPS for production APIs
- Validate incoming reports
- Authenticate authority operations
- Protect emergency communication
- Use signed packets for mesh communication
- Reject duplicate/expired mesh packets

---

# 📊 Technology Stack

### Frontend

- React
- Vite
- Leaflet
- Recharts
- Service Worker
- IndexedDB

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL / Supabase
- PostGIS

### AI / ML

- Python
- PyTorch
- NumPy
- scikit-learn
- Scientific/geospatial processing libraries

### Scientific Data

- INSAT-3DR
- MOSDAC
- IMDAA
- QPE
- DEM

### Mobile / Connectivity

- Kotlin
- Android
- Bluetooth
- Wi-Fi Direct

---

# 🌐 System Architecture

```text
                 ┌───────────────────────┐
                 │     DATA SOURCES      │
                 │                       │
                 │ INSAT-3DR             │
                 │ IMDAA                 │
                 │ QPE                   │
                 │ DEM                   │
                 │ Hazard Observations   │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │ DATA PROCESSING       │
                 │                       │
                 │ Calibration           │
                 │ Quality Control       │
                 │ Spatial Alignment     │
                 │ Feature Engineering   │
                 │ Temporal Sequences    │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │   SPATIOTEMPORAL ML   │
                 │                       │
                 │ Shared Backbone       │
                 │        │              │
                 │ ┌──────┼──────┐       │
                 │ ▼      ▼      ▼       │
                 │Storm  Cloud   Flood   │
                 │Head   Head    Head    │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │ CALIBRATION & RISK    │
                 │                       │
                 │ Probabilities         │
                 │ Thresholds            │
                 │ Risk Zones            │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │ FASTAPI + DATABASE    │
                 │                       │
                 │ Forecasts             │
                 │ Zones                 │
                 │ Reports               │
                 │ Emergencies           │
                 └───────────┬───────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌───────────────┐         ┌───────────────┐
        │ Web Dashboard │         │ Offline / Mesh │
        │ Authorities   │         │ Emergency SOS │
        │ Citizens      │         │               │
        └───────────────┘         └───────────────┘
```

---

# 👥 Intended Users

### Citizens

- Receive hazard warnings
- View risk maps
- Submit reports
- Send emergency SOS
- Use offline/mesh communication

### Authorities

- Monitor hazard probability maps
- Identify affected zones
- Review citizen reports
- Coordinate emergency resources
- Monitor emergency communications

---

# 📜 Disclaimer

BharatRiskAI is a research and prototype system.

Its predictions should not be treated as a replacement for official meteorological or disaster-management warnings.

The scientific forecasting performance depends on the availability, quality, coverage and reliability of historical observations and training labels.

---

# Vision

BharatRiskAI aims to combine **space-based observations, atmospheric science, machine learning and resilient communication infrastructure** into a unified early-warning platform for India.

> **Powered by satellite observations.  
> Informed by atmospheric science.  
> Enhanced by AI.  
> Designed for resilience.**

---

## 📄 License

See the `LICENSE` file in this repository.
