import { getGeolocationErrorStatus } from "./geolocation";

export function haversineKm(a, b) {
  const toRadians = (value) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const latDelta = toRadians(b.lat - a.lat);
  const lonDelta = toRadians(b.lon - a.lon);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const arc = Math.sin(latDelta / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(lonDelta / 2) ** 2;
  return 2 * earthRadiusKm * Math.asin(Math.sqrt(arc));
}

export function buildOsmEmbedUrl(lat, lon) {
  const left = lon - 0.12;
  const right = lon + 0.12;
  const top = lat + 0.08;
  const bottom = lat - 0.08;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${left}%2C${bottom}%2C${right}%2C${top}&layer=mapnik&marker=${lat}%2C${lon}`;
}

export function buildGoogleMapsUrl(location) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location)}`;
}

export function formatDistanceChip(itemLocation, geolocationState, locationEntry) {
  if (!itemLocation) return "No location";
  if (geolocationState.status === "denied") return "Location blocked";
  if (geolocationState.status === "unavailable") return "Location unavailable";
  if (geolocationState.status === "error") return "Retry location";
  if (geolocationState.status === "prompt" || geolocationState.status === "idle") return "Enable location";
  if (geolocationState.status === "requesting") return "Requesting location...";
  if (!geolocationState.coords) return "Locating you...";
  if (!locationEntry || locationEntry.status === "loading") return "Finding place...";
  if (locationEntry.status === "error") return "Lookup failed";
  return `~${haversineKm(geolocationState.coords, locationEntry.coords).toFixed(1)} km from you`;
}

export function formatGeolocationStatus(geolocationState) {
  if (geolocationState.status === "ready") return "Distance enabled";
  if (geolocationState.status === "requesting") return "Requesting location...";
  if (geolocationState.status === "denied") return "Location blocked in browser permissions";
  if (geolocationState.status === "unavailable") {
    return geolocationState.unavailableReason === "insecure-context"
      ? "Location is unavailable in this browser context"
      : "Location is not supported in this browser";
  }
  if (geolocationState.status === "error") return "Location request failed. Try again.";
  return "Enable location to show distances";
}

export function getGeolocationButtonLabel(geolocationState) {
  if (geolocationState.status === "ready") return "Refresh location";
  if (geolocationState.status === "requesting") return "Requesting...";
  if (geolocationState.status === "error") return "Retry location";
  if (geolocationState.status === "unavailable") {
    return geolocationState.unavailableReason === "insecure-context" ? "Location requires HTTPS" : "Location unsupported";
  }
  return "Enable location";
}

export function createPositionRequester(updateGeolocationState, inFlightRef) {
  return function requestCurrentPosition() {
    if (!navigator.geolocation) {
      updateGeolocationState({ status: "unavailable", coords: null, unavailableReason: "unsupported" });
      return;
    }
    if (!window.isSecureContext) {
      updateGeolocationState({ status: "unavailable", coords: null, unavailableReason: "insecure-context" });
      return;
    }
    if (inFlightRef.current) {
      return;
    }
    inFlightRef.current = true;
    updateGeolocationState((current) => ({
      status: "requesting",
      coords: current.status === "ready" ? current.coords : null,
      unavailableReason: null,
    }));
    navigator.geolocation.getCurrentPosition(
      (position) => {
        inFlightRef.current = false;
        updateGeolocationState({ status: "ready", coords: { lat: position.coords.latitude, lon: position.coords.longitude }, unavailableReason: null });
      },
      (error) => {
        inFlightRef.current = false;
        const permissionStatus = navigator.permissions?.query;
        if (typeof permissionStatus !== "function") {
          updateGeolocationState({ status: getGeolocationErrorStatus({ errorCode: error?.code }), coords: null, unavailableReason: null });
          return;
        }
        permissionStatus
          .call(navigator.permissions, { name: "geolocation" })
          .then((permission) => updateGeolocationState({ status: getGeolocationErrorStatus({ errorCode: error?.code, permissionState: permission.state }), coords: null, unavailableReason: null }))
          .catch(() => updateGeolocationState({ status: getGeolocationErrorStatus({ errorCode: error?.code }), coords: null, unavailableReason: null }));
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
    );
  };
}
