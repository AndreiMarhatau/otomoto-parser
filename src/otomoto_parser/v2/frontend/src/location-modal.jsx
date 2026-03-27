import React from "react";
import {
  Alert,
  Dialog,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from "@mui/material";

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
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle sx={{ pr: 16 }}>
        <Typography component="div" variant="overline" color="text.secondary">Map preview</Typography>
        <Typography component="div" variant="h5">{preview.title}</Typography>
        <Typography component="div" variant="body2" color="text.secondary">{preview.location}</Typography>
        <Stack direction="row" spacing={1} sx={{ position: "absolute", right: 16, top: 14 }}>
          <IconButton title="Open map" href={buildGoogleMapsUrl(preview.location)} tone="secondary"><IconExternal /></IconButton>
          <IconButton title="Refresh preview" tone="secondary" onClick={() => setCoords(null)}><IconRefresh /></IconButton>
          <IconButton title="Close preview" tone="secondary" onClick={onClose}><IconClose /></IconButton>
        </Stack>
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {loading ? <Alert severity="info">Loading map preview...</Alert> : null}
          {geoError ? <Alert severity="error">{geoError}</Alert> : null}
          {coords ? <iframe title={`${preview.title} map`} src={buildOsmEmbedUrl(coords.lat, coords.lon)} style={{ width: "100%", minHeight: 420, border: 0, borderRadius: 16 }} /> : null}
          {userCoords ? <Typography variant="body2" color="text.secondary">Your location is available for distance calculations.</Typography> : null}
        </Stack>
      </DialogContent>
    </Dialog>
  );
}
