import json
z = json.load(open("zones.json"))
for a in z: print(a["name"], a["elevation_m"], a["dist_to_river_km"])
r = json.load(open("rain_2026-02-18.json"))
for k, v in r.items():
    p = v.get("precipitation", [])
    real = [x for x in p if x is not None]
    print(k, "nulls:", len(p) - len(real), "total mm:", round(sum(real), 1), "max/hr:", max(real, default=None))
t = json.load(open("tide_test.json"))
print([round(x, 2) if x is not None else None for x in t["hourly"]["sea_level_height_msl"]])

r = json.load(open("rain_2026-02-18.json"))["Urdesa"]["precipitation"]
t = json.load(open("tide_test.json"))["hourly"]["sea_level_height_msl"]
for h in range(24):
    print(f"{h:02d}:00  rain {r[h]:5.1f} mm   tide {t[h]:5.2f} m")