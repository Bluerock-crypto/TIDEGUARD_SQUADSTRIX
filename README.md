# TideGuard
Tide-aware flood risk and ambulance rerouting for Guayaquil (HACK2IMPACT 2026)

## Frontend replay

The browser dashboard is in `index.html`. Serve the repository root over HTTP
(for example, `python -m http.server 8000`) and open `http://localhost:8000`;
opening the HTML file directly will prevent the browser from loading the local
replay JSON files.

The dashboard loads the historical zone, rainfall, and offshore tide data from
`data/`, then requests `/risk` and `/route` from the same origin using the
parameters in [API_CONTRACT.md](API_CONTRACT.md). If those endpoints are not
available, it shows a clearly labeled simulated preview. The preview's zone
risk scores, route geometry, road-risk proxy, and travel times are illustrative
only and must not be used as navigation or treated as verified road closures.
Leaflet, map tiles, and fonts are loaded from their public CDNs.
