from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.risk_stub import get_zone_risks    # swap to: from backend.risk import get_zone_risks
from backend import router

app = FastAPI(title="TideGuard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Point(BaseModel):
    lat: float
    lon: float


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/risk")
def risk(hour: int | None = None, rain: float | None = None,
         tide: float | None = None, mode: str = "tideguard"):
    return get_zone_risks(hour=hour, rain=rain, tide=tide, mode=mode)


@app.get("/route")
def route(from_lat: float = -2.1709, from_lon: float = -79.9078,
          hour: int | None = None, mode: str = "tideguard"):
    zones = get_zone_risks(hour=hour, mode=mode)["zones"]
    return router.compute_route(zones, from_lat, from_lon)


@app.post("/block")
def block(p: Point):
    router.block(p.lat, p.lon)
    return {"ok": True}


@app.post("/reset")
def reset():
    router.reset()
    return {"ok": True}