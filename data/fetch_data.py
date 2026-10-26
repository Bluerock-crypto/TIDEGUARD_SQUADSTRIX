import json, math, requests
import osmnx as ox

# ---- 1. ZONES (approximate coords: verify on a map, edit freely) ----
ZONES = [
    # name, lat, lon, known_trouble_spot
    ("Urdesa",            -2.1709, -79.9078, 1),
    ("Av 9 de Octubre",   -2.1895, -79.8895, 1),
    ("Av Barcelona",      -2.1280, -79.9120, 1),
    ("Isla Trinitaria",   -2.2500, -79.9000, 1),
    ("Monte Sinai",       -2.0800, -79.9500, 1),
    ("Febres Cordero",    -2.2050, -79.9300, 0),
    ("Alborada",          -2.1400, -79.9000, 0),
    ("Guasmo Central",    -2.2500, -79.8900, 0),
]
RIVER_REF = (-2.1930, -79.8810)  # one fixed riverfront point (approximate)

def km(a, b):
    R = 6371
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dlat/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(h))

lats = ",".join(str(z[1]) for z in ZONES)
lons = ",".join(str(z[2]) for z in ZONES)
elev = requests.get("https://api.open-meteo.com/v1/elevation",
                    params={"latitude": lats, "longitude": lons}).json()["elevation"]

zones = [{"name": n, "lat": la, "lon": lo, "elevation_m": e,
          "dist_to_river_km": round(km((la, lo), RIVER_REF), 2),
          "known_trouble_spot": t}
         for (n, la, lo, t), e in zip(ZONES, elev)]
json.dump(zones, open("zones.json", "w"), indent=2)
print("zones.json saved")

# ---- 2. RAIN for 18 Feb 2026, per zone ----
rain = {}
for z in zones:
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": z["lat"], "longitude": z["lon"],
        "start_date": "2026-02-18", "end_date": "2026-02-18",
        "hourly": "precipitation", "timezone": "America/Guayaquil"}).json()
    rain[z["name"]] = r.get("hourly", {})
json.dump(rain, open("rain_2026-02-18.json", "w"))
print("rain saved (open it: are the values null or real?)")

# ---- 3. TIDE test (Gulf of Guayaquil point, may return nulls) ----
t = requests.get("https://marine-api.open-meteo.com/v1/marine", params={
    "latitude": -2.7, "longitude": -80.3,
    "hourly": "sea_level_height_msl",
    "start_date": "2026-02-18", "end_date": "2026-02-18",
    "timezone": "America/Guayaquil"}).json()
json.dump(t, open("tide_test.json", "w"))
vals = t.get("hourly", {}).get("sea_level_height_msl", [])
print("tide usable" if vals and any(v is not None for v in vals)
      else "tide NOT usable: write 'tide: simulated' in NOTES.txt")

# ---- 4. ROAD GRAPH ----
G = ox.graph_from_point((-2.195, -79.90), dist=6000, network_type="drive")
ox.save_graphml(G, "roads.graphml")
print("roads saved:", len(G.nodes), "nodes")

hosp = ox.features_from_point((-2.195, -79.90), tags={"amenity": "hospital"}, dist=6000)
for _, h in hosp.iterrows():
    print("hospital:", h.get("name"))

# ---- 5. PATH CHECK: Urdesa -> graph -> any node near the hospital ----
import networkx as nx
src = ox.distance.nearest_nodes(G, -79.9078, -2.1709)
dst = ox.distance.nearest_nodes(G, -79.8953, -2.2178)  # approx hospital area
print("path exists:", nx.has_path(G, src, dst))