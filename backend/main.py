from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.risk_stub import get_zone_risks

app = FastAPI(title="TideGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

blocked_roads: set[tuple[float, float]] = set()


@app.get("/risk")
def risk(
    hour: int | None = None,
    rain: float | None = None,
    tide: float | None = None,
    mode: str = "tideguard",
):
    """Return the risk payload for the 8 zones in data/zones.json."""
    return get_zone_risks(hour=hour, rain=rain, tide=tide, mode=mode)


@app.get("/route")
def route(
    from_lat: float | None = None,
    from_lon: float | None = None,
    hour: int | None = None,
    mode: str = "tideguard",
):
    """Return the fake route payload defined by the API contract."""
    return {
        "status": "ok",
        "original": {
            "coords": [[-2.1770, -79.9075], [-2.1730, -79.9040], [-2.1709, -79.9078]],
            "minutes": 14,
            "at_risk_roads": 3,
        },
        "tideguard": {
            "coords": [[-2.1770, -79.9075], [-2.1688, -79.9150], [-2.1709, -79.9078]],
            "minutes": 18,
            "at_risk_roads": 0,
        },
        "reason": "Urdesa at risk 4-7 AM, rerouted",
    }


@app.post("/block")
async def block(payload: dict[str, float]):
    """Store blocked road coordinates in memory for the current running app."""
    lat = float(payload["lat"])
    lon = float(payload["lon"])
    blocked_roads.add((lat, lon))
    return {"ok": True}


@app.post("/reset")
async def reset():
    """Clear the in-memory blocked road set."""
    blocked_roads.clear()
    return {"ok": True}


@app.get("/health")
def health():
    """Simple liveness check for local deploys and smoke tests."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
