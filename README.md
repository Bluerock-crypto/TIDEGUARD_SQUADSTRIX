# TideGuard
Tide-aware flood risk and ambulance rerouting for Guayaquil (HACK2IMPACT 2026)

## Backend API skeleton

Install dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Run the API:

```bash
uvicorn backend.main:app --reload
```

The app listens on http://127.0.0.1:8000 by default.

### Curl examples

```bash
curl "http://127.0.0.1:8000/risk?hour=7&mode=tideguard"
curl "http://127.0.0.1:8000/risk?rain=12&tide=0.8"
curl "http://127.0.0.1:8000/route?from_lat=-2.1709&from_lon=-79.9078&hour=7&mode=tideguard"
curl -X POST "http://127.0.0.1:8000/block" -H "Content-Type: application/json" -d '{"lat": -2.1709, "lon": -79.9078}'
curl -X POST "http://127.0.0.1:8000/reset"
curl "http://127.0.0.1:8000/health"
```

## Notes

- The risk layer is intentionally stubbed in `backend/risk_stub.py` and can be replaced later by `backend/risk.py` with a single import swap in `backend/main.py`.
- The route endpoint is a placeholder hardcoded response that matches the contract shape but does not yet compute a real route.
