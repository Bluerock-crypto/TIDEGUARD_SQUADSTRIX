"""
TideGuard Risk Engine - Backend 1
Translates rain forecast and tidal sea levels into zone-by-zone flood risk scores,
vulnerability assessments, and danger windows for Guayaquil, Ecuador.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
# pyrefly: ignore[missing-import]
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ==============================================================================
# MODEL PARAMETERS & ASSUMPTIONS (Commented Prototype Assumptions)
# ==============================================================================

# Weights for Vulnerability (V) calculation
# Prototype assumption: Hand-labelled known trouble spots provide the primary flood
# vulnerability signal (0.40), while inverted elevation (0.30) and inverted river
# distance (0.30) capture geographic proximity and low-lying drainage impediments.
WEIGHTS: Dict[str, float] = {
    "known_trouble_spot": 0.40,  # prototype assumption
    "elevation": 0.30,           # prototype assumption
    "dist_to_river": 0.30,       # prototype assumption
}

# Rain saturation cap in mm/hr
# Prototype assumption: 20 mm/hr represents torrential rainfall where street drainage
# reaches maximum capacity (rain_n = min(rain_mm_hr / 20.0, 1.0)).
RAIN_CAP: float = 20.0  # prototype assumption

# Risk classification thresholds
# Prototype assumption: Risk >= 0.66 is 'high', >= 0.33 is 'medium', otherwise 'low'.
HIGH_RISK_THRESHOLD: float = 0.66    # prototype assumption
MEDIUM_RISK_THRESHOLD: float = 0.33  # prototype assumption
DANGER_THRESHOLD: float = 0.66       # prototype assumption

# Simulated sine tide parameter
# Prototype assumption: Guayaquil semi-diurnal tidal cycle has an approximate 12.4-hour period.
SIMULATED_TIDE_PERIOD_HOURS: float = 12.4  # prototype assumption

# Source identification labels per API_CONTRACT.md
SOURCE_REPLAY_RAIN: str = "replay 2026-02-18"
SOURCE_REPLAY_TIDE: str = "offshore model"
SOURCE_SLIDER: str = "slider"
SOURCE_SIMULATED_TIDE: str = "simulated"

# Data file paths
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
ZONES_FILE: Path = DATA_DIR / "zones.json"
RAIN_FILE: Path = DATA_DIR / "rain_2026-02-18.json"
TIDE_FILE: Path = DATA_DIR / "tide_test.json"

# ==============================================================================
# DATA LOADING & VULNERABILITY CALCULATION
# ==============================================================================

def load_zones_data() -> List[Dict[str, Any]]:
    """Load zone definitions from zones.json."""
    if not ZONES_FILE.exists():
        raise FileNotFoundError(f"Zones file not found at {ZONES_FILE}")
    with open(ZONES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_rain_data() -> Dict[str, Dict[str, Any]]:
    """Load 24-hour rainfall replay data for 18 Feb 2026."""
    if not RAIN_FILE.exists():
        raise FileNotFoundError(f"Rain replay file not found at {RAIN_FILE}")
    with open(RAIN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_simulated_tide() -> List[float]:
    """Generate 24 hourly sea level values using a 12.4-hour sine wave."""
    simulated: List[float] = []
    for h in range(24):
        # Sine wave oscillating around 0 with amplitude ~1.0
        val = math.sin(2 * math.pi * h / SIMULATED_TIDE_PERIOD_HOURS)
        simulated.append(round(val, 2))
    return simulated

def load_tide_data() -> tuple[List[float], str]:
    """
    Load hourly sea level height data for 18 Feb 2026.
    Falls back to a simulated 12.4h sine wave if file is missing, invalid, or null.
    """
    if not TIDE_FILE.exists():
        return generate_simulated_tide(), SOURCE_SIMULATED_TIDE
    try:
        with open(TIDE_FILE, "r", encoding="utf-8") as f:
            tide_json = json.load(f)
        hourly_vals = tide_json.get("hourly", {}).get("sea_level_height_msl", [])
        if not hourly_vals or len(hourly_vals) < 24 or any(v is None for v in hourly_vals[:24]):
            return generate_simulated_tide(), SOURCE_SIMULATED_TIDE
        return [float(v) for v in hourly_vals[:24]], SOURCE_REPLAY_TIDE
    except Exception:
        return generate_simulated_tide(), SOURCE_SIMULATED_TIDE

def compute_vulnerabilities(zones: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Compute vulnerability V (0 to 1) for each zone as a weighted sum of min-max normalized fields.
    - Elevation: Lower elevation is more vulnerable -> inverted normalization.
    - Distance to river: Closer to river is more vulnerable -> inverted normalization.
    - Known trouble spot: 1 is high, 0 is low.
    """
    elevations = [z["elevation_m"] for z in zones]
    distances = [z["dist_to_river_km"] for z in zones]

    min_elev, max_elev = min(elevations), max(elevations)
    min_dist, max_dist = min(distances), max(distances)

    vulnerabilities: Dict[str, float] = {}
    for z in zones:
        # Inverted min-max: (max - x) / (max - min) so lower values get higher normalized scores
        elev_norm = (max_elev - z["elevation_m"]) / (max_elev - min_elev) if max_elev != min_elev else 0.5
        dist_norm = (max_dist - z["dist_to_river_km"]) / (max_dist - min_dist) if max_dist != min_dist else 0.5
        trouble_norm = float(z["known_trouble_spot"])

        v = (
            WEIGHTS["known_trouble_spot"] * trouble_norm +
            WEIGHTS["elevation"] * elev_norm +
            WEIGHTS["dist_to_river"] * dist_norm
        )
        # Bounded between 0 and 1, rounded to 2 decimal places
        vulnerabilities[z["name"]] = round(min(max(v, 0.0), 1.0), 2)

    return vulnerabilities

# Initialize zone definitions and calculated vulnerability scores
ZONES_DATA: List[Dict[str, Any]] = load_zones_data()
ZONE_VULNERABILITY: Dict[str, float] = compute_vulnerabilities(ZONES_DATA)

# ==============================================================================
# STARTUP VALIDATION & RANKING DISPLAY
# ==============================================================================

def print_startup_vulnerability_ranking() -> None:
    """Print all zones ranked by V at startup, and flag any anomaly warnings."""
    ranked = sorted(ZONES_DATA, key=lambda z: ZONE_VULNERABILITY[z["name"]], reverse=True)
    
    print("\n" + "=" * 80)
    print("TIDEGUARD RISK ENGINE - VULNERABILITY RANKING (STARTUP)")
    print("=" * 80)
    print(f"{'Rank':4} | {'Zone Name':18} | {'Vulnerability (V)':17} | {'Elev (m)':8} | {'Dist River (km)':15} | {'Trouble Spot':12}")
    print("-" * 80)
    for idx, z in enumerate(ranked, start=1):
        name = z["name"]
        v = ZONE_VULNERABILITY[name]
        print(f"{idx:4} | {name:18} | {v:17.2f} | {z['elevation_m']:8.1f} | {z['dist_to_river_km']:15.2f} | {z['known_trouble_spot']:12}")
    print("=" * 80)

    # Sanity check: verify lowest-lying zone is in top 3
    min_elev = min(z["elevation_m"] for z in ZONES_DATA)
    top_3_elevations = [z["elevation_m"] for z in ranked[:3]]
    if min_elev not in top_3_elevations:
        print(f"[WARNING] Ranking anomaly: The lowest-lying zone ({min_elev}m) is NOT in the top 3 ranked zones!")

    # Warning for any zone with V < 0.66
    for z in ranked:
        v = ZONE_VULNERABILITY[z["name"]]
        if v < HIGH_RISK_THRESHOLD:
            print(f"[WARNING] Zone '{z['name']}' has V = {v:.2f} < {HIGH_RISK_THRESHOLD:.2f} (risk can never reach 'high' level).")
    print("=" * 80 + "\n")

# Run startup ranking display immediately upon module load
print_startup_vulnerability_ranking()

# ==============================================================================
# DANGER WINDOW CALCULATION
# ==============================================================================

def merge_danger_windows(danger_hours: List[int]) -> Optional[Dict[str, int]]:
    """
    Merge consecutive danger hours across a one-hour dip (e.g. 17, 18, 20, 21 becomes 17 to 21).
    Returns the longest window as {"start_hour": start, "end_hour": end}, or None if no danger hours.
    """
    if not danger_hours:
        return None

    sorted_hours = sorted(set(danger_hours))
    windows: List[tuple[int, int]] = []
    w_start = sorted_hours[0]
    w_end = sorted_hours[0]

    for h in sorted_hours[1:]:
        # If consecutive (diff == 1) or one-hour dip (diff == 2), extend the current window
        if h - w_end <= 2:
            w_end = h
        else:
            windows.append((w_start, w_end))
            w_start = h
            w_end = h
    windows.append((w_start, w_end))

    # Select the longest window by hour span (end - start + 1)
    longest = max(windows, key=lambda w: (w[1] - w[0] + 1))
    return {"start_hour": longest[0], "end_hour": longest[1]}

def calculate_replay_danger_windows(mode: str = "tideguard") -> Dict[str, Optional[Dict[str, int]]]:
    """
    Compute the danger window for each zone across hours 0-23 of the 18 Feb 2026 replay day.
    Hours where risk > DANGER_THRESHOLD (0.66) are flagged as danger hours.
    """
    rain_data = load_rain_data()
    tide_values, _ = load_tide_data()

    min_tide = min(tide_values)
    max_tide = max(tide_values)
    tide_range = max_tide - min_tide if max_tide != min_tide else 1.0

    windows: Dict[str, Optional[Dict[str, int]]] = {}

    for z in ZONES_DATA:
        name = z["name"]
        v = ZONE_VULNERABILITY[name]
        zone_precip = rain_data.get(name, {}).get("precipitation", [0.0] * 24)

        danger_hours: List[int] = []
        for h in range(24):
            rain_mm = zone_precip[h] if h < len(zone_precip) else 0.0
            rain_n = min(max(rain_mm / RAIN_CAP, 0.0), 1.0)

            if mode == "tideguard":
                tide_n = (tide_values[h] - min_tide) / tide_range
                tide_n = min(max(tide_n, 0.0), 1.0)
                risk = v * rain_n * (1.0 + tide_n) / 2.0
            else:
                # rain_only mode: tide_n = 0
                risk = v * rain_n * (1.0 + 0.0) / 2.0

            if risk > DANGER_THRESHOLD:
                danger_hours.append(h)

        windows[name] = merge_danger_windows(danger_hours)

    return windows

# ==============================================================================
# IMPORTABLE FUNCTION (Step 5)
# ==============================================================================

def get_zone_risk(
    hour: Optional[int] = None,
    mode: str = "tideguard",
    rain: Optional[float] = None,
    tide: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate flood risk scores, danger levels, and danger windows for all zones.

    Exposes the core risk model for internal API routes and external modules (e.g. router).

    Parameters:
    -----------
    hour : int, optional
        Hour of the replay day (0 to 23) for 18 Feb 2026. Required for replay mode.
    mode : str, default "tideguard"
        Risk computation mode: "tideguard" (considers tide) or "rain_only" (tide_n = 0).
    rain : float, optional
        Rainfall rate in mm/hr (>= 0). Used in slider override mode.
    tide : float, optional
        Normalized tide level (0.0 to 1.0). Used in slider override mode.

    Returns:
    --------
    dict:
        {
            "inputs": {
                "rain_mm_hr": float,
                "tide_m": float,
                "rain_source": str,
                "tide_source": str
            },
            "zones": [
                {
                    "name": str,
                    "lat": float,
                    "lon": float,
                    "vulnerability": float,
                    "risk": float,
                    "level": "low" | "medium" | "high",
                    "danger_window": {"start_hour": int, "end_hour": int} or None
                },
                ...
            ]
        }

    Raises:
    -------
    ValueError:
        If inputs are missing, out of bounds, or invalid.
    """
    if mode not in ("tideguard", "rain_only"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'tideguard' or 'rain_only'.")

    # Determine whether call is slider mode or replay mode
    is_slider = rain is not None or tide is not None

    if is_slider:
        if rain is None or tide is None:
            raise ValueError("Slider mode requires both 'rain' (mm/hr) and 'tide' (0 to 1) parameters.")
        if rain < 0:
            raise ValueError(f"Invalid rain value {rain}. Rain cannot be negative.")
        if not (0.0 <= tide <= 1.0):
            raise ValueError(f"Invalid tide value {tide}. Slider tide must be between 0.0 and 1.0.")

        rain_mm_hr = float(rain)
        tide_m = float(tide)
        rain_source = SOURCE_SLIDER
        tide_source = SOURCE_SLIDER

        rain_n = min(rain_mm_hr / RAIN_CAP, 1.0)
        tide_n = tide_m if mode == "tideguard" else 0.0

        zone_results = []
        for z in ZONES_DATA:
            v = ZONE_VULNERABILITY[z["name"]]
            risk = v * rain_n * (1.0 + tide_n) / 2.0
            risk_rounded = round(min(max(risk, 0.0), v), 2)

            if risk_rounded >= HIGH_RISK_THRESHOLD:
                level = "high"
            elif risk_rounded >= MEDIUM_RISK_THRESHOLD:
                level = "medium"
            else:
                level = "low"

            zone_results.append({
                "name": z["name"],
                "lat": z["lat"],
                "lon": z["lon"],
                "vulnerability": v,
                "risk": risk_rounded,
                "level": level,
                "danger_window": None,  # null for slider overrides per API contract
            })

    else:
        # Replay mode
        if hour is None:
            raise ValueError("Must provide either 'hour' (0-23) for replay mode, or 'rain' and 'tide' for slider mode.")
        if not isinstance(hour, int) or hour < 0 or hour > 23:
            raise ValueError(f"Invalid hour {hour}. Must be an integer between 0 and 23.")

        rain_data = load_rain_data()
        tide_values, tide_source = load_tide_data()

        min_tide = min(tide_values)
        max_tide = max(tide_values)
        tide_range = max_tide - min_tide if max_tide != min_tide else 1.0

        tide_m = round(tide_values[hour], 2)
        rain_source = SOURCE_REPLAY_RAIN

        # Normalization for tide
        raw_tide_n = (tide_values[hour] - min_tide) / tide_range
        tide_n = min(max(raw_tide_n, 0.0), 1.0) if mode == "tideguard" else 0.0

        # Precompute danger windows across the 24 hours of 18 Feb 2026
        danger_windows = calculate_replay_danger_windows(mode=mode)

        # Replay top-level rain is the maximum/reference rainfall recorded at this hour
        max_rain_hour = max(
            rain_data.get(z["name"], {}).get("precipitation", [0.0] * 24)[hour]
            for z in ZONES_DATA
        )
        rain_mm_hr = round(max_rain_hour, 1)

        zone_results = []
        for z in ZONES_DATA:
            name = z["name"]
            v = ZONE_VULNERABILITY[name]
            zone_rain = rain_data.get(name, {}).get("precipitation", [0.0] * 24)[hour]
            rain_n = min(max(zone_rain / RAIN_CAP, 0.0), 1.0)

            risk = v * rain_n * (1.0 + tide_n) / 2.0
            risk_rounded = round(min(max(risk, 0.0), v), 2)

            if risk_rounded >= HIGH_RISK_THRESHOLD:
                level = "high"
            elif risk_rounded >= MEDIUM_RISK_THRESHOLD:
                level = "medium"
            else:
                level = "low"

            zone_results.append({
                "name": name,
                "lat": z["lat"],
                "lon": z["lon"],
                "vulnerability": v,
                "risk": risk_rounded,
                "level": level,
                "danger_window": danger_windows.get(name),
            })

    return {
        "inputs": {
            "rain_mm_hr": rain_mm_hr,
            "tide_m": tide_m,
            "rain_source": rain_source,
            "tide_source": tide_source,
        },
        "zones": zone_results,
    }

# ==============================================================================
# FASTAPI APPLICATION & ENDPOINTS
# ==============================================================================

app = FastAPI(
    title="TideGuard Risk Engine API",
    description="Flood risk scoring and danger window identification for Guayaquil ambulances.",
    version="1.0.0",
)

# Enable CORS for all origins as required
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/risk")
def get_risk(
    hour: Optional[int] = None,
    mode: str = "tideguard",
    rain: Optional[float] = None,
    tide: Optional[float] = None,
) -> Dict[str, Any]:
    """
    GET /risk endpoint conforming strictly to API_CONTRACT.md.
    Supports replay queries (?hour=7&mode=tideguard) and slider queries (?rain=12&tide=0.8).
    """
    try:
        return get_zone_risk(hour=hour, mode=mode, rain=rain, tide=tide)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("risk_engine:app", host="0.0.0.0", port=8000, reload=True)
