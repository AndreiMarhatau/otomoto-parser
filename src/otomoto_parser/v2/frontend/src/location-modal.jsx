import React from "react";

import { IconClose, IconExternal, IconRefresh } from "./icons";
import { IconButton } from "./layout";
import { buildGoogleMapsUrl, buildOsmEmbedUrl } from "./location-utils";

export function LocationModal({ preview, onClose }) {
  const [coords, setCoords] = React.useState(null);
  const [geoError, setGeoError] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [userCoords, setUserCoords] = React.useState(null);

  React.useEffect(() => {
    if (!preview) return undefined;
    const controller = new AbortController();
    let active = true;
    async function lookupLocation() {
      setLoading(true);
      setGeoError(null);
      try {
        const response = await fetch(`/api/geocode?query=${encodeURIComponent(preview.location)}`, { signal: controller.signal });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "Could not load map preview.");
        if (active) setCoords(payload.item);
      } catch (error) {
        if (active && error.name !== "AbortError") setGeoError(error.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    lookupLocation();
    return () => { active = false; controller.abort(); };
  }, [preview]);

  React.useEffect(() => {
    if (!preview || !navigator.geolocation) return undefined;
    let active = true;
    navigator.geolocation.getCurrentPosition((position) => {
      if (active) setUserCoords({ lat: position.coords.latitude, lon: position.coords.longitude });
    });
    return () => { active = false; };
  }, [preview]);

  if (!preview) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div><p className="eyebrow">Map preview</p><h2>{preview.title}</h2><p className="muted">{preview.location}</p></div>
          <div className="modal-head-actions">
            <IconButton title="Open map" href={buildGoogleMapsUrl(preview.location)} tone="secondary"><IconExternal /></IconButton>
            <IconButton title="Refresh preview" tone="secondary" onClick={() => setCoords(null)}><IconRefresh /></IconButton>
            <IconButton title="Close preview" tone="secondary" onClick={onClose}><IconClose /></IconButton>
          </div>
        </div>
        {loading ? <p className="progress-box">Loading map preview...</p> : null}
        {geoError ? <p className="error-text">{geoError}</p> : null}
        {coords ? <iframe title={`${preview.title} map`} className="map-frame" src={buildOsmEmbedUrl(coords.lat, coords.lon)} /> : null}
        {userCoords ? <p className="muted">Your location is available for distance calculations.</p> : null}
      </div>
    </div>
  );
}
