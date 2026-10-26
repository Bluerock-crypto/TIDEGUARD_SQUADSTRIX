from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "zones.json"


def _load_zones() -> list[dict[str, Any]]:
    with DATA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def get_zone_risks(hour=None, rain=None, tide=None, mode="tideguard"):
    """Return the risk payload shape defined in API_CONTRACT.md.

    This stub is intentionally fixed so the real engine can later replace it
    without changing the endpoint contract or import path.
    """
    rain_value = float(rain) if rain is not None else 15.3
    tide_value = float(tide) if tide is not None else 0.16

    # Fixed dummy values for the 8 zones in data/zones.json.
    dummy_profiles = [
        {"vulnerability": 0.94, "risk": 0.71, "level": "high", "danger_window": {"start_hour": 4, "end_hour": 7}},
        {"vulnerability": 0.88, "risk": 0.67, "level": "medium", "danger_window": {"start_hour": 5, "end_hour": 8}},
        {"vulnerability": 0.64, "risk": 0.49, "level": "medium", "danger_window": {"start_hour": 6, "end_hour": 9}},
        {"vulnerability": 0.91, "risk": 0.74, "level": "high", "danger_window": {"start_hour": 3, "end_hour": 6}},
        {"vulnerability": 0.58, "risk": 0.42, "level": "low", "danger_window": {"start_hour": 7, "end_hour": 10}},
        {"vulnerability": 0.73, "risk": 0.56, "level": "medium", "danger_window": {"start_hour": 5, "end_hour": 8}},
        {"vulnerability": 0.81, "risk": 0.61, "level": "medium", "danger_window": {"start_hour": 4, "end_hour": 7}},
        {"vulnerability": 0.86, "risk": 0.68, "level": "high", "danger_window": {"start_hour": 2, "end_hour": 5}},
    ]

    zones = _load_zones()
    result = []

    for zone, profile in zip(zones, dummy_profiles):
        result.append(
            {
                "name": zone["name"],
                "lat": zone["lat"],
                "lon": zone["lon"],
                "vulnerability": profile["vulnerability"],
                "risk": profile["risk"],
                "level": profile["level"],
                "danger_window": profile["danger_window"],
            }
        )

    return {
        "inputs": {
            "rain_mm_hr": rain_value,
            "tide_m": tide_value,
            "rain_source": "replay 2026-02-18",
            "tide_source": "offshore model",
        },
        "zones": result,
    }
