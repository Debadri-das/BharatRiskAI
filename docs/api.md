# API

All endpoints are prefixed with `/api`.

`GET /dashboard` returns statistics, zones, recommendations, reports, emergencies, and risk trend.

`POST /simulation` accepts:

```json
{"rainfall_percentage":30,"drainage_efficiency_delta":-40,"duration_hours":24,"zone_ids":[1]}
```

`POST /report` accepts citizen latitude, longitude, water level, severity, description, and optional photo URL. The backend attaches it to the nearest zone and recalculates risk.

`POST /emergency` accepts emergency type, location, people count, vulnerable groups, and optional description. Priority is calculated locally.
