# TideGuard API contract

GET /risk?hour=7&mode=tideguard      (mode: tideguard | rain_only)
GET /risk?rain=12&tide=0.8           (slider override: rain mm/hr, tide 0-1)
-> {
  "inputs": {"rain_mm_hr": 15.3, "tide_m": 0.16, "rain_source": "replay 2026-02-18", "tide_source": "offshore model"},
  "zones": [
    {"name": "Urdesa", "lat": -2.1709, "lon": -79.9078,
     "vulnerability": 0.94, "risk": 0.71, "level": "high",
     "danger_window": {"start_hour": 4, "end_hour": 7}}
  ]
}

GET /route?from_lat=..&from_lon=..&hour=7&mode=tideguard
-> {
  "status": "ok",                      (or "no_safe_route")
  "original":  {"coords": [[lat, lon], ...], "minutes": 14, "at_risk_roads": 3},
  "tideguard": {"coords": [[lat, lon], ...], "minutes": 18, "at_risk_roads": 0},
  "reason": "Urdesa at risk 4-7 AM, rerouted"
}

POST /block   body: {"lat": .., "lon": ..}   -> marks nearest road confirmed blocked
POST /reset                                  -> clears blocked roads