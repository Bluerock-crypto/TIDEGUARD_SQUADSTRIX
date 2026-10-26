"""Real routing for TideGuard: Dijkstra on the OSM road graph (NetworkX).
original  = shortest by length (ignores risk)
tideguard = length * (1 + K * risk), blocked roads removed."""
from pathlib import Path
import networkx as nx
import numpy as np
import osmnx as ox

ROOT = Path(__file__).resolve().parent.parent
HOSPITAL = (-2.2178, -79.8953)   # approx. hospital area: verify on openstreetmap.org
K = 3.0                          # risk penalty strength
RADIUS_KM = 1.5                  # a zone's risk spreads this far over roads
AT_RISK = 0.33
SPEED_MS = 8.3                   # ~30 km/h, minutes are an estimate

# ---- load once at startup, simplify to one edge per (u, v) ----
_G = ox.load_graphml(ROOT / "data" / "roads.graphml")
H = nx.DiGraph()
for u, v, d in _G.edges(data=True):
    L = float(d.get("length", 1.0))
    if not H.has_edge(u, v) or L < H[u][v]["length"]:
        H.add_edge(u, v, length=L)
for n, d in _G.nodes(data=True):
    H.add_node(n, lat=float(d["y"]), lon=float(d["x"]))

NODES = np.array(list(H.nodes()))
N_LAT = np.array([H.nodes[n]["lat"] for n in NODES])
N_LON = np.array([H.nodes[n]["lon"] for n in NODES])
EDGES = list(H.edges())
E_LAT = np.array([(H.nodes[u]["lat"] + H.nodes[v]["lat"]) / 2 for u, v in EDGES])
E_LON = np.array([(H.nodes[u]["lon"] + H.nodes[v]["lon"]) / 2 for u, v in EDGES])
BLOCKED = set()


def _km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2 +
         np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * np.arcsin(np.sqrt(a))


def nearest_node(lat, lon):
    return NODES[int(np.argmin(_km(lat, lon, N_LAT, N_LON)))]


def edge_risks(zones):
    """risk per edge = max risk of any zone within RADIUS_KM of the edge midpoint."""
    risk = np.zeros(len(EDGES))
    for z in zones:
        near = _km(z["lat"], z["lon"], E_LAT, E_LON) <= RADIUS_KM
        risk = np.where(near, np.maximum(risk, z["risk"]), risk)
    return {e: float(r) for e, r in zip(EDGES, risk)}


def _summary(path, risk):
    coords = [[H.nodes[n]["lat"], H.nodes[n]["lon"]] for n in path]
    edges = list(zip(path[:-1], path[1:]))
    length = sum(H[u][v]["length"] for u, v in edges)
    return {"coords": coords,
            "minutes": round(length / SPEED_MS / 60, 1),
            "at_risk_roads": sum(1 for e in edges if risk[e] >= AT_RISK)}


def compute_route(zones, from_lat, from_lon):
    risk = edge_risks(zones)
    src, dst = nearest_node(from_lat, from_lon), nearest_node(*HOSPITAL)
    try:
        orig = nx.shortest_path(H, src, dst, weight="length")
    except nx.NetworkXNoPath:
        return {"status": "no_safe_route", "reason": "No road connection found"}

    def cost(u, v, d):
        if (u, v) in BLOCKED:
            return None                      # hidden from the search
        return d["length"] * (1 + K * risk[(u, v)])

    try:
        safe = nx.shortest_path(H, src, dst, weight=cost)
    except nx.NetworkXNoPath:
        return {"status": "no_safe_route", "original": _summary(orig, risk),
                "reason": "Every route is blocked"}
    o, s = _summary(orig, risk), _summary(safe, risk)
    if orig == safe:
        reason = "Risk is low on the shortest route: no change needed"
    else:
        reason = (f"Rerouted: at-risk roads {o['at_risk_roads']} -> {s['at_risk_roads']}, "
                  f"{s['minutes'] - o['minutes']:+.1f} min (estimated)")
    return {"status": "ok", "original": o, "tideguard": s, "reason": reason}


def block(lat, lon):
    i = int(np.argmin(_km(lat, lon, E_LAT, E_LON)))
    u, v = EDGES[i]
    BLOCKED.add((u, v))
    if H.has_edge(v, u):
        BLOCKED.add((v, u))


def reset():
    BLOCKED.clear()
    