import React from "react";

import { api } from "./api";
import { createPositionRequester } from "./location-utils";
import { getInitialGeolocationPlan } from "./geolocation";

export function useResultsGeolocation(results, currentItems) {
  const [geolocationState, setGeolocationState] = React.useState({ status: "idle", coords: null, unavailableReason: null });
  const [locationCache, setLocationCache] = React.useState({});
  const geolocationRequestInFlightRef = React.useRef(false);
  const geolocationStateRef = React.useRef({ status: "idle", coords: null, unavailableReason: null });

  const updateGeolocationState = React.useCallback((nextStateOrUpdater) => {
    setGeolocationState((current) => {
      const nextState = typeof nextStateOrUpdater === "function" ? nextStateOrUpdater(current) : nextStateOrUpdater;
      geolocationStateRef.current = nextState;
      return nextState;
    });
  }, []);

  const requestCurrentPosition = React.useMemo(() => createPositionRequester(updateGeolocationState, geolocationRequestInFlightRef), [updateGeolocationState]);

  React.useEffect(() => {
    if (!results) return;
    if (!navigator.geolocation) return updateGeolocationState({ status: "unavailable", coords: null, unavailableReason: "unsupported" });
    if (!window.isSecureContext) return updateGeolocationState({ status: "unavailable", coords: null, unavailableReason: "insecure-context" });
    if (typeof navigator.permissions?.query !== "function") {
      return updateGeolocationState((current) => current.status === "ready" || current.status === "requesting" ? current : { status: "prompt", coords: null, unavailableReason: null });
    }
    let active = true;
    let permissionRef = null;
    navigator.permissions.query({ name: "geolocation" }).then((permissionStatus) => {
      if (!active) return;
      permissionRef = permissionStatus;
      const syncPermissionState = () => {
        if (!active) return;
        const nextPlan = getInitialGeolocationPlan({ hasGeolocation: Boolean(navigator.geolocation), isSecureContext: window.isSecureContext, hasPermissionsApi: true, permissionState: permissionStatus.state });
        const current = geolocationStateRef.current;
        if (nextPlan.shouldRequestPosition && !geolocationRequestInFlightRef.current && (current.status !== "ready" || !current.coords)) return requestCurrentPosition();
        if (nextPlan.status === "prompt" && (current.status === "requesting" || current.status === "ready")) return;
        if (current.status !== nextPlan.status || current.coords !== null) updateGeolocationState({ status: nextPlan.status, coords: null, unavailableReason: null });
      };
      syncPermissionState();
      permissionStatus.onchange = syncPermissionState;
    }).catch(() => {
      if (!active) return;
      updateGeolocationState((current) => (
        current.status === "ready" || current.status === "requesting" || current.status === "denied"
          ? current
          : { status: "prompt", coords: null, unavailableReason: null }
      ));
    });
    return () => { active = false; if (permissionRef) permissionRef.onchange = null; };
  }, [requestCurrentPosition, results, updateGeolocationState]);

  React.useEffect(() => {
    if (!geolocationState.coords) return;
    const uniqueLocations = [...new Set(currentItems.map((item) => item.location).filter(Boolean))];
    const now = Date.now();
    const missingLocations = uniqueLocations.filter((location) => !locationCache[location] || (locationCache[location].status === "error" && (locationCache[location].retryAt || 0) <= now));
    if (missingLocations.length === 0) return;
    setLocationCache((current) => ({ ...current, ...Object.fromEntries(missingLocations.map((location) => [location, { status: "loading" }])) }));
    api("/api/geocode/batch", { method: "POST", body: JSON.stringify({ queries: missingLocations }) })
      .then((payload) => setLocationCache((current) => ({ ...current, ...Object.fromEntries(missingLocations.map((location) => [location, payload.items?.[location] ? { status: "ready", coords: { lat: payload.items[location].lat, lon: payload.items[location].lon } } : { status: "error", retryAt: Date.now() + 15000 }])) })))
      .catch(() => setLocationCache((current) => ({ ...current, ...Object.fromEntries(missingLocations.map((location) => [location, { status: "error", retryAt: Date.now() + 15000 }])) })));
  }, [currentItems, geolocationState.coords, locationCache]);

  return { geolocationState, locationCache, requestCurrentPosition, updateGeolocationState };
}
