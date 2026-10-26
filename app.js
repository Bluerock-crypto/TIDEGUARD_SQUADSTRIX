(() => {
  "use strict";

  const DEFAULT_HOUR = 7;
  const ORIGIN = [-2.1709, -79.9078];
  const DESTINATION = [-2.145, -79.936];
  const $ = (id) => document.getElementById(id);
  const inputs = {
    hour: $("hour-slider"),
    rain: $("rain-slider"),
    tide: $("tide-slider"),
  };
  const output = {
    hour: $("hour-output"),
    rain: $("rain-output"),
    tide: $("tide-output"),
  };
  const state = {
    zones: [],
    rainData: null,
    tideData: null,
    riskApi: false,
    routeApi: false,
    rainManual: false,
    tideManual: false,
    timer: null,
  };

  const map = L.map("map", { zoomControl: false, scrollWheelZoom: false }).setView([-2.184, -79.906], 12);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  const zoneLayer = L.layerGroup().addTo(map);
  const routeLayer = L.layerGroup().addTo(map);

  function setConnection(message, kind) {
    const element = $("connection-status");
    element.className = `connection-status${kind ? ` ${kind}` : ""}`;
    element.lastElementChild.textContent = message;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function hourLabel(hour) {
    return `${String(hour).padStart(2, "0")}:00`;
  }

  function seriesValue(data, zoneName, hour) {
    const series = data && data[zoneName];
    return series && Array.isArray(series.precipitation) ? Number(series.precipitation[hour]) : null;
  }

  function replayRain(hour) {
    const candidates = state.zones.map((zone) => seriesValue(state.rainData, zone.name, hour)).filter(Number.isFinite);
    return candidates.length ? Math.max(...candidates) : 0;
  }

  function replayTide(hour) {
    const series = state.tideData && state.tideData.hourly;
    return series && Array.isArray(series.sea_level_height_msl) ? Number(series.sea_level_height_msl[hour]) : 0;
  }

  function setSourceTag(element, text, kind) {
    element.textContent = text;
    element.className = `source-tag ${kind}`;
  }

  function updateOutputs() {
    output.hour.value = hourLabel(Number(inputs.hour.value));
    output.rain.value = Number(inputs.rain.value).toFixed(1);
    output.tide.value = Number(inputs.tide.value).toFixed(2);
    setSourceTag($("rain-source"), state.rainManual ? "SIMULATED" : "REAL REPLAY", state.rainManual ? "source-simulated" : "source-real");
    setSourceTag($("tide-source"), state.tideManual ? "SIMULATED" : "OFFSHORE TIDE", state.tideManual ? "source-simulated" : "source-offshore");
  }

  function simulatedRisk(zone, rain, tide) {
    const rainFactor = clamp(rain / 20, 0, 1);
    const tideFactor = clamp((tide + 0.9) / 2.3, 0, 1);
    const troubleFactor = Number(zone.known_trouble_spot) ? 0.19 : 0.05;
    const lowElevationFactor = clamp((12 - Number(zone.elevation_m || 6)) / 12, 0, 1) * 0.10;
    const riverFactor = clamp((8 - Number(zone.dist_to_river_km || 8)) / 8, 0, 1) * 0.09;
    return clamp(rainFactor * 0.42 + tideFactor * 0.15 + troubleFactor + lowElevationFactor + riverFactor, 0, 1);
  }

  function levelFor(risk) {
    if (risk >= 0.67) return "high";
    if (risk >= 0.52) return "moderate";
    return "low";
  }

  function riskColor(level) {
    return level === "high" ? "#f16e67" : level === "moderate" ? "#e6c66d" : "#52d2bd";
  }

  function normalizeZones(zones, rain, tide, useApi) {
    if (!Array.isArray(zones)) return [];
    return zones.filter((zone) => Number.isFinite(Number(zone.lat)) && Number.isFinite(Number(zone.lon))).map((zone) => {
      const risk = useApi && Number.isFinite(Number(zone.risk)) ? Number(zone.risk) : simulatedRisk(zone, rain, tide);
      const apiLevel = useApi && zone.level ? String(zone.level).toLowerCase() : "";
      const level = apiLevel === "medium" ? "moderate" : apiLevel || levelFor(risk);
      return { ...zone, risk, level };
    });
  }

  function renderZones(zones) {
    zoneLayer.clearLayers();
    zones.forEach((zone) => {
      const color = riskColor(zone.level);
      const circle = L.circle([Number(zone.lat), Number(zone.lon)], {
        radius: 1000,
        color,
        weight: 1.5,
        opacity: 0.85,
        fillColor: color,
        fillOpacity: 0.17,
      });
      const popup = `<div class="zone-popup"><strong>${escapeHtml(zone.name || "Risk zone")}</strong><span>Risk ${Math.round(zone.risk * 100)}% · ${escapeHtml(zone.level)}<br>Approx. 1 km radius${zone.danger_window ? `<br>Danger window ${zone.danger_window.start_hour}:00–${zone.danger_window.end_hour}:00` : ""}</span></div>`;
      circle.bindPopup(popup);
      circle.addTo(zoneLayer);
    });
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  async function requestRisk(hour, rain, tide) {
    const query = new URLSearchParams({ hour, mode: "tideguard", rain: rain.toFixed(1), tide: tide.toFixed(2) });
    const response = await fetch(`/risk?${query}`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Risk API returned HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.zones)) throw new Error("Risk API response is missing its zones array");
    return data.zones;
  }

  async function requestRoute(hour, rain, tide) {
    const query = new URLSearchParams({
      from_lat: String(ORIGIN[0]),
      from_lon: String(ORIGIN[1]),
      hour: String(hour),
      mode: "tideguard",
      rain: rain.toFixed(1),
      tide: tide.toFixed(2),
    });
    const response = await fetch(`/route?${query}`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Route API returned HTTP ${response.status}`);
    const data = await response.json();
    if (!data.original || !Array.isArray(data.original.coords)) throw new Error("Route API response is missing original route coordinates");
    if (data.status === "ok" && (!data.tideguard || !Array.isArray(data.tideguard.coords))) {
      throw new Error("Route API response is missing TideGuard route coordinates");
    }
    return data;
  }

  function makePreviewRoute(zones) {
    const atRisk = zones.filter((zone) => zone.level === "high" || zone.risk >= 0.55);
    const hazard = [...atRisk].sort((a, b) => b.risk - a.risk)[0];
    const original = [ORIGIN, [-2.162, -79.916], DESTINATION];
    let rerouted = original;
    if (hazard) {
      const latDirection = hazard.lat < (ORIGIN[0] + DESTINATION[0]) / 2 ? 1 : -1;
      const lonDirection = hazard.lon < (ORIGIN[1] + DESTINATION[1]) / 2 ? -1 : 1;
      rerouted = [ORIGIN, [hazard.lat + latDirection * 0.014, hazard.lon + lonDirection * 0.013], DESTINATION];
    }
    return {
      status: "ok",
      original: { coords: original, minutes: 14, at_risk_roads: atRisk.length },
      tideguard: { coords: rerouted, minutes: 14 + (atRisk.length ? Math.max(2, atRisk.length * 2) : 0), at_risk_roads: 0 },
      reason: hazard
        ? `${hazard.name} is elevated at ${hourLabel(Number(inputs.hour.value))}; preview route bends away from the highest-risk zone.`
        : "No high-risk zones in the preview; the route stays close to the original.",
      preview: true,
      atRiskZones: atRisk,
    };
  }

  function validCoords(coords) {
    return Array.isArray(coords) && coords.length >= 2 && coords.every((point) =>
      Array.isArray(point) && point.length >= 2 && Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1])));
  }

  function marker(position, label, extraClass) {
    return L.marker(position, {
      icon: L.divIcon({
        className: "",
        html: `<span class="route-marker ${extraClass || ""}">${label}</span>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
      keyboard: false,
    });
  }

  function displayRoutes(route, zones) {
    routeLayer.clearLayers();
    const originalCoords = route.original && route.original.coords;
    const safeCoords = route.tideguard && route.tideguard.coords;
    if (validCoords(originalCoords)) {
      L.polyline(originalCoords, { color: "#f2b361", weight: 4, opacity: .9, dashArray: "9 8", lineCap: "round" }).addTo(routeLayer);
    }
    if (route.status === "ok" && validCoords(safeCoords)) {
      L.polyline(safeCoords, { color: "#52d2bd", weight: 5, opacity: .98, lineCap: "round" }).addTo(routeLayer);
    }
    marker(ORIGIN, "A", "").bindTooltip("Ambulance start").addTo(routeLayer);
    marker(DESTINATION, "H", "destination").bindTooltip("Hospital destination (preview)").addTo(routeLayer);
    const bounds = L.latLngBounds([ORIGIN, DESTINATION]);
    zones.forEach((zone) => bounds.extend([Number(zone.lat), Number(zone.lon)]));
    if (validCoords(originalCoords)) originalCoords.forEach((point) => bounds.extend(point));
    if (route.status === "ok" && validCoords(safeCoords)) safeCoords.forEach((point) => bounds.extend(point));
    map.fitBounds(bounds, { paddingTopLeft: [40, 70], paddingBottomRight: [40, 40], maxZoom: 13 });
  }

  function renderSummary(route, zones) {
    const originalMinutes = Number(route.original && route.original.minutes);
    const newMinutes = Number(route.tideguard && route.tideguard.minutes);
    const extra = Number.isFinite(originalMinutes) && Number.isFinite(newMinutes) ? Math.max(0, newMinutes - originalMinutes) : null;
    const apiRiskCount = route.original && Number(route.original.at_risk_roads);
    const riskCount = Number.isFinite(apiRiskCount) ? apiRiskCount : zones.filter((zone) => zone.level !== "low").length;
    const preview = Boolean(route.preview);

    $("roads-value").textContent = preview ? `${riskCount} zone${riskCount === 1 ? "" : "s"}` : Number.isFinite(apiRiskCount) ? String(apiRiskCount) : `${riskCount} zones`;
    $("roads-note").textContent = preview ? "Zone proxy · simulated, not road-level" : "Reported by the route API";
    $("minutes-value").textContent = extra === null ? "—" : `+${extra}`;
    $("minutes-note").textContent = extra === null ? "Route timing unavailable" : "minutes vs. original route";
    $("reason-value").textContent = route.status === "no_safe_route"
      ? "No safe route found for these conditions."
      : route.reason || "Route adjusted for current risk conditions.";
    $("reason-note").textContent = preview ? "Illustrative local route preview · not turn-by-turn" : "Route assessment from TideGuard";
    $("route-mode").textContent = preview ? "SIMULATED" : "TIDEGUARD API";
    $("route-mode").className = `source-tag ${preview ? "source-simulated" : "source-real"}`;
    $("route-status").innerHTML = route.status === "no_safe_route"
      ? "<span></span> No safe route"
      : riskCount > 0 ? "<span></span> Risk detected · reroute preview" : "<span></span> Route clear";
    $("route-status").classList.toggle("is-alert", route.status === "no_safe_route" || riskCount > 0);
    $("route-disclaimer").textContent = preview
      ? "Fallback route, travel times, and risk estimates are simulated previews. Zone counts are only a proxy for roads at risk—not verified closures or turn-by-turn guidance."
      : "Decision support only. Risk zones and route estimates are not a substitute for verified road closures or local navigation.";
  }

  async function updateReplay() {
    const hour = Number(inputs.hour.value);
    const rain = Number(inputs.rain.value);
    const tide = Number(inputs.tide.value);
    updateOutputs();
    setConnection("Refreshing risk and route…", "");

    const [riskResult, routeResult] = await Promise.allSettled([
      requestRisk(hour, rain, tide),
      requestRoute(hour, rain, tide),
    ]);
    state.riskApi = riskResult.status === "fulfilled";
    state.routeApi = routeResult.status === "fulfilled";
    const zoneSource = state.riskApi ? riskResult.value : state.zones;
    const zones = normalizeZones(zoneSource, rain, tide, state.riskApi);
    state.zones = zones;
    renderZones(zones);
    const route = state.routeApi ? routeResult.value : makePreviewRoute(zones);
    displayRoutes(route, zones);
    renderSummary(route, zones);

    if (state.riskApi && state.routeApi) {
      setConnection("Connected · live risk & route API", "is-api");
    } else {
      const failed = [riskResult, routeResult].filter((result) => result.status === "rejected");
      const detail = failed.map((result) => result.reason instanceof Error ? result.reason.message : String(result.reason)).join("; ");
      setConnection(`Local replay preview · API unavailable (${detail})`, "is-error");
    }
  }

  function scheduleUpdate() {
    window.clearTimeout(state.timer);
    state.timer = window.setTimeout(() => {
      updateReplay().catch((error) => {
        setConnection(`Replay update failed: ${error instanceof Error ? error.message : String(error)}`, "is-error");
      });
    }, 180);
  }

  inputs.hour.addEventListener("input", () => {
    const hour = Number(inputs.hour.value);
    if (!state.rainManual) inputs.rain.value = replayRain(hour).toFixed(1);
    if (!state.tideManual) inputs.tide.value = replayTide(hour).toFixed(2);
    scheduleUpdate();
  });
  inputs.rain.addEventListener("input", () => {
    state.rainManual = true;
    $("rain-hint").textContent = "Manual slider override · simulated rainfall";
    scheduleUpdate();
  });
  inputs.tide.addEventListener("input", () => {
    state.tideManual = true;
    $("tide-hint").textContent = "Manual slider override · simulated tide";
    scheduleUpdate();
  });
  $("reset-replay").addEventListener("click", () => {
    state.rainManual = false;
    state.tideManual = false;
    const hour = Number(inputs.hour.value);
    inputs.rain.value = replayRain(hour).toFixed(1);
    inputs.tide.value = replayTide(hour).toFixed(2);
    $("rain-hint").textContent = "Rainfall from the selected replay hour";
    $("tide-hint").textContent = "Coarse offshore model; not an estuary gauge";
    scheduleUpdate();
  });

  async function initialize() {
    const dataResults = await Promise.allSettled([
      fetch("data/zones.json").then((response) => {
        if (!response.ok) throw new Error(`zones.json returned HTTP ${response.status}`);
        return response.json();
      }),
      fetch("data/rain_2026-02-18.json").then((response) => {
        if (!response.ok) throw new Error(`rain replay returned HTTP ${response.status}`);
        return response.json();
      }),
      fetch("data/tide_test.json").then((response) => {
        if (!response.ok) throw new Error(`tide replay returned HTTP ${response.status}`);
        return response.json();
      }),
    ]);
    const [zonesResult, rainResult, tideResult] = dataResults;
    if (zonesResult.status === "fulfilled" && Array.isArray(zonesResult.value)) state.zones = zonesResult.value;
    if (rainResult.status === "fulfilled") state.rainData = rainResult.value;
    if (tideResult.status === "fulfilled") state.tideData = tideResult.value;
    const missing = dataResults.filter((result) => result.status === "rejected");
    if (!state.zones.length) {
      const detail = missing.map((result) => result.reason instanceof Error ? result.reason.message : String(result.reason)).join("; ");
      setConnection(`Could not load local zones: ${detail}`, "is-error");
      $("reason-value").textContent = "Replay data unavailable.";
      $("reason-note").textContent = "Serve this page from the project root to load local data.";
      return;
    }
    if (missing.length) {
      setConnection("Some replay data unavailable; using available zone data", "is-error");
    }
    inputs.hour.value = String(DEFAULT_HOUR);
    inputs.rain.value = replayRain(DEFAULT_HOUR).toFixed(1);
    inputs.tide.value = replayTide(DEFAULT_HOUR).toFixed(2);
    updateOutputs();
    await updateReplay();
  }

  initialize().catch((error) => {
    setConnection(`Could not initialize replay: ${error instanceof Error ? error.message : String(error)}`, "is-error");
  });
})();
