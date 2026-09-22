# Data readiness

## Status

Blocked for supervised training: 99 hazard-timestamp targets remain unknown (null means unknown, never negative) and 0 confirmed labels exist. Configured proxy labels (thunderstorm satellite signature, cloudburst QPE threshold) are recorded as label_type=proxy and never presented as observed truth; flash_flood has no evaluable overlapping input at all, so supervised sequences cannot be completed.

- Timestamp count (feature grids): 49
- Date range: 2023-07-01T00:15:28+00:00 to 2024-06-18T12:00:00+00:00
- Independent dates/events: 2 (only 1 usable L1C date; the single QPE sample is a separate date)
- Positive labels: 47
- Negative labels: 1
- Unknown labels: 99
- Per hazard: {"thunderstorm": {"confirmed_positive": 0, "confirmed_negative": 0, "proxy_positive": 47, "proxy_negative": 0, "positive": 47, "negative": 0, "unknown": 2}, "cloudburst": {"confirmed_positive": 0, "confirmed_negative": 0, "proxy_positive": 0, "proxy_negative": 1, "positive": 0, "negative": 1, "unknown": 48}, "flash_flood": {"confirmed_positive": 0, "confirmed_negative": 0, "proxy_positive": 0, "proxy_negative": 0, "positive": 0, "negative": 0, "unknown": 49}}
- Ground-truth event sources: none
- IMDAA: missing
- CMV: missing
- Official thunderstorm, cloudburst, and flood records: missing
- Train/validation/test feasibility: not feasible (0/0/0); fewer than 3 independent event/date groups exist and hazard targets remain incomplete (unknown records), so no split is created.

## Missing sources

- IMDAA pressure-level reanalysis (data/imdaa)
- CMV cloud-motion vectors (data/insat/cmv, optional)
- official lightning/thunderstorm event catalogue
- official cloudburst event catalogue with authoritative threshold
- official flood/inundation observations (gauge, extent, or disaster reports)
- contemporaneous multi-date INSAT L1C + QPE sequences

## Exact additional data required before meaningful training

1. INSAT-3DR L1C imager granules for at least 3+ independent dates covering real weather events (thunderstorm, cloudburst, and flood episodes), each with a full 30-minute sequence usable for +2h..+6h horizons.
2. Contemporaneous INSAT QPE (HEM) for those same dates so 1h/3h/6h accumulations can be computed from actual timestamps.
3. IMDAA pressure-level profiles (temperature, humidity, pressure, u/v wind) for the same dates to derive IWV, CAPE, CIN, shear, and convergence.
4. At least one authoritative thunderstorm/lightning observation source (e.g., lightning detection network or IMD storm reports) to create confirmed thunderstorm labels.
5. An authoritative cloudburst definition/threshold plus observed rainfall reports for label confirmation.
6. Official flood/inundation observations (gauge exceedance, satellite-derived flood extent, or disaster management reports) for flash-flood labels.
7. Optional: INSAT CMV products for atmospheric motion features.

A smoke-test model may exercise tensor plumbing only; it must not be reported as trained or evaluated.
