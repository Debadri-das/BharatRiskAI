# Architecture

BharatRisk AI has four cooperating layers:

1. React authority dashboard and citizen emergency UI.
2. FastAPI service layer with SQLite persistence.
3. Local ML training/inference modules.
4. Android Kotlin mesh-SOS prototype.

The frontend can continue with cached demo data and IndexedDB queues if the API is unavailable. The backend seeds Kolkata demo zones, recalculates risk after reports, and exposes simulation and recommendation endpoints. The Android app owns the realistic mesh responsibility; the web app only shows mesh state and bridge results.
