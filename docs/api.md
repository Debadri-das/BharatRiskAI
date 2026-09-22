# API

All endpoints are prefixed with `/api`.

`GET /dashboard` returns statistics, zones, recommendations, reports, emergencies, and risk trend.

The simulation endpoint has been removed. Live nowcast data is read from the
latest decoded MOSDAC/INSAT-3D and IMDAA products:

- `GET /nowcast/city?live=true`
- `GET /nowcast/zone/{zone_id}?live=true`
- `GET /nowcast/alerts?live=true`
- `GET /satellite/status`

`POST /report` accepts citizen latitude, longitude, water level, severity, description, and optional photo URL. The backend attaches it to the nearest zone and recalculates risk.

`POST /emergency` accepts emergency type, location, people count, vulnerable groups, and optional description. Priority is calculated locally.
