import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useNavigate, useParams } from "react-router-dom";
import "./styles.css";

const systemCategoryOrder = [
  "Price evaluation out of range",
  "Data not verified",
  "Imported from US",
  "To be checked",
];

const inProgressStatuses = new Set(["pending", "running", "categorizing"]);
const pageSizeOptions = [12, 24, 48];

function haversineKm(a, b) {
  const toRadians = (value) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const latDelta = toRadians(b.lat - a.lat);
  const lonDelta = toRadians(b.lon - a.lon);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);

  const sinLat = Math.sin(latDelta / 2);
  const sinLon = Math.sin(lonDelta / 2);
  const arc =
    sinLat * sinLat +
    Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;

  return 2 * earthRadiusKm * Math.asin(Math.sqrt(arc));
}

function buildOsmEmbedUrl(lat, lon) {
  const lonDelta = 0.12;
  const latDelta = 0.08;
  const left = lon - lonDelta;
  const right = lon + lonDelta;
  const top = lat + latDelta;
  const bottom = lat - latDelta;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${left}%2C${bottom}%2C${right}%2C${top}&layer=mapnik&marker=${lat}%2C${lon}`;
}

function buildGoogleMapsUrl(location) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location)}`;
}

function formatDistanceChip(itemLocation, geolocationState, locationEntry) {
  if (!itemLocation) {
    return "No location";
  }
  if (geolocationState.status === "denied") {
    return "Location blocked";
  }
  if (geolocationState.status === "unavailable") {
    return "Location unavailable";
  }
  if (!geolocationState.coords) {
    return "Locating you...";
  }
  if (!locationEntry || locationEntry.status === "loading") {
    return "Finding place...";
  }
  if (locationEntry.status === "error") {
    return "Lookup failed";
  }
  const distanceKm = haversineKm(geolocationState.coords, locationEntry.coords);
  return `~${distanceKm.toFixed(1)} km from you`;
}

function formatFieldLabel(key) {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^./, (char) => char.toUpperCase());
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "—";
  }
  return String(value);
}

function scrollWindowToPosition(top) {
  window.scrollTo(0, top);
  if (document.scrollingElement) {
    document.scrollingElement.scrollTop = top;
  }
  document.documentElement.scrollTop = top;
  document.body.scrollTop = top;
}

function IconRefresh() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 12a8 8 0 1 1-2.34-5.66" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M20 4v6h-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M9 7V4h6v3M8 7l1 12h6l1-12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconExternal() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14 5h5v5M19 5l-8 8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M19 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconReport() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 4h8l4 4v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M16 4v4h4M9 12h6M9 16h6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconCheckBadge() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2l2.1 2.3 3.1-.3 1.2 2.8 2.8 1.2-.3 3.1L23 13l-2.1 2.3.3 3.1-2.8 1.2-1.2 2.8-3.1-.3L12 24l-2.3-2.1-3.1.3-1.2-2.8-2.8-1.2.3-3.1L1 13l2.1-2.3-.3-3.1 2.8-1.2 1.2-2.8 3.1.3z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M8.5 12.5l2.3 2.3 4.7-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconXBadge() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2l2.1 2.3 3.1-.3 1.2 2.8 2.8 1.2-.3 3.1L23 13l-2.1 2.3.3 3.1-2.8 1.2-1.2 2.8-3.1-.3L12 24l-2.3-2.1-3.1.3-1.2-2.8-2.8-1.2.3-3.1L1 13l2.1-2.3-.3-3.1 2.8-1.2 1.2-2.8 3.1.3z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconChevronLeft() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14.5 6.5L9 12l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconChevronRight() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9.5 6.5L15 12l-5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 20l4.5-1 9-9-3.5-3.5-9 9L4 20z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M12.5 6.5L16 10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconTag() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M11 4H5v6l8 8 6-6-8-8z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <circle cx="8" cy="8" r="1.2" fill="currentColor" />
    </svg>
  );
}

function IconStar() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3.8l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8L12 3.8z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  );
}

function buildPageItems(currentPage, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);
  const normalized = [...pages].filter((page) => page >= 1 && page <= totalPages).sort((a, b) => a - b);
  const items = [];
  for (const page of normalized) {
    const previous = items[items.length - 1];
    if (typeof previous === "number" && page - previous > 1) {
      items.push("ellipsis");
    }
    items.push(page);
  }
  return items;
}

function IconButton({ title, onClick, href, disabled = false, tone = "default", children }) {
  const className = `icon-button icon-button-${tone}${disabled ? " icon-button-disabled" : ""}`;
  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className} title={title} aria-label={title}>
        {children}
      </a>
    );
  }

  return (
    <button type="button" className={className} title={title} aria-label={title} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

function CategoryPicker({ item, categories, busy, onCommit, onCreateCategory, onOpenChange }) {
  const [open, setOpen] = React.useState(false);
  const [draftKeys, setDraftKeys] = React.useState(item.savedCategoryKeys || []);
  const [saving, setSaving] = React.useState(false);
  const containerRef = React.useRef(null);
  const selectedKeys = new Set(draftKeys);
  const selectedCount = categories.filter((category) => selectedKeys.has(category.key)).length;

  React.useEffect(() => {
    onOpenChange?.(open);
  }, [onOpenChange, open]);

  React.useEffect(() => {
    if (!open) {
      setDraftKeys(item.savedCategoryKeys || []);
    }
  }, [item.savedCategoryKeys, open]);

  function orderedKeys(keys) {
    const selected = new Set(keys);
    return categories.map((category) => category.key).filter((key) => selected.has(key));
  }

  async function closePicker() {
    setOpen(false);
    const nextKeys = orderedKeys(draftKeys);
    const currentKeys = orderedKeys(item.savedCategoryKeys || []);
    if (JSON.stringify(nextKeys) === JSON.stringify(currentKeys)) {
      return;
    }
    setSaving(true);
    try {
      await onCommit(item, nextKeys);
    } finally {
      setSaving(false);
    }
  }

  React.useEffect(() => {
    if (!open) {
      return undefined;
    }
    function handlePointerDown(event) {
      if (!containerRef.current?.contains(event.target)) {
        void closePicker();
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [draftKeys, item, open]);

  function toggleCategory(categoryKey) {
    const next = new Set(draftKeys);
    if (next.has(categoryKey)) {
      next.delete(categoryKey);
    } else {
      next.add(categoryKey);
    }
    setDraftKeys(orderedKeys([...next]));
  }

  async function handleCreateCategory() {
    const created = await onCreateCategory();
    if (!created) {
      return;
    }
    setDraftKeys((current) => [...new Set([...current, created.key])]);
  }

  return (
    <div
      className={open ? "category-picker open" : "category-picker"}
      ref={containerRef}
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      <button
        type="button"
        className="listing-category-button chip-interactive"
        onClick={() => {
          if (open) {
            void closePicker();
            return;
          }
          setOpen(true);
        }}
        disabled={busy || saving}
        title="Manage saved categories"
      >
        <IconTag />
        <span>Save</span>
        {selectedCount > 0 ? <span className="listing-category-count">{selectedCount}</span> : null}
      </button>
      {open ? (
        <div className="category-picker-menu">
          <div className="category-picker-list">
            {categories.map((category) => (
              <label key={category.key} className="category-picker-option">
                <input
                  type="checkbox"
                  checked={selectedKeys.has(category.key)}
                  disabled={busy || saving}
                  onChange={() => toggleCategory(category.key)}
                />
                <span className="category-picker-option-label">
                  {category.key === "Favorites" ? <IconStar /> : <IconTag />}
                  <span>{category.label}</span>
                </span>
              </label>
            ))}
          </div>
          <button
            type="button"
            className="category-picker-add"
            disabled={busy || saving}
            onClick={() => void handleCreateCategory()}
          >
            <IconPlus />
            <span>Add new</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Ignore invalid JSON for error payloads.
    }
    throw new Error(detail);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

function usePolling(loader, enabled) {
  const [state, setState] = React.useState({ loading: true, error: null, data: null });

  const load = React.useCallback(async () => {
    try {
      const data = await loader();
      setState({ loading: false, error: null, data });
      return data;
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error }));
      throw error;
    }
  }, [loader]);

  React.useEffect(() => {
    let active = true;

    async function run() {
      try {
        const data = await loader();
        if (active) {
          setState({ loading: false, error: null, data });
        }
      } catch (error) {
        if (active) {
          setState({ loading: false, error, data: null });
        }
      }
    }

    run();
    if (!enabled) {
      return () => {
        active = false;
      };
    }

    const timer = window.setInterval(run, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [enabled, loader]);

  return { ...state, reload: load };
}

function Shell({ title, children }) {
  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Otomoto Parser</p>
          <h1>{title}</h1>
        </div>
        <Link to="/" className="hero-link">
          All requests
        </Link>
      </header>
      {children}
    </div>
  );
}

function Breadcrumbs({ items }) {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumbs">
      {items.map((item, index) => (
        <React.Fragment key={item.label}>
          {index > 0 ? <span>/</span> : null}
          {item.to ? <Link to={item.to}>{item.label}</Link> : <span>{item.label}</span>}
        </React.Fragment>
      ))}
    </nav>
  );
}

function StatusPill({ status }) {
  return <span className={`status-pill status-${status}`}>{status}</span>;
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}

function RequestListPage() {
  const navigate = useNavigate();
  const [url, setUrl] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState(null);
  const { data, loading, reload } = usePolling(() => api("/api/requests"), true);

  async function submit(event) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const payload = await api("/api/requests", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      navigate(`/requests/${payload.item.id}`);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setCreating(false);
    }
  }

  async function removeRequest(requestId) {
    const request = items.find((item) => item.id === requestId);
    if (request && inProgressStatuses.has(request.status)) {
      window.alert("This request is still running and cannot be removed yet.");
      return;
    }
    if (!window.confirm("Remove this request and its stored files?")) {
      return;
    }
    try {
      await api(`/api/requests/${requestId}`, { method: "DELETE" });
      await reload();
    } catch (removeError) {
      window.alert(removeError.message);
    }
  }

  const items = data?.items || [];

  return (
    <Shell title="Version 2 workspace">
      <section className="panel panel-grid">
        <div className="panel-block">
          <h2>Create request</h2>
          <p className="muted">
            Paste an Otomoto search URL. The backend starts parsing immediately and keeps progress in history.
          </p>
          <form className="request-form" onSubmit={submit}>
            <textarea
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://www.otomoto.pl/osobowe/..."
              rows={5}
              required
            />
            <div className="form-actions">
              <button type="submit" disabled={creating}>
                {creating ? "Creating..." : "Create request"}
              </button>
              <IconButton title="Refresh request list" tone="secondary" onClick={() => reload()}>
                <IconRefresh />
              </IconButton>
            </div>
            {error ? <p className="error-text">{error}</p> : null}
          </form>
        </div>

        <div className="panel-block">
          <h2>History</h2>
          {loading ? <p className="muted">Loading requests...</p> : null}
          {!loading && items.length === 0 ? <p className="muted">No requests yet.</p> : null}
          <div className="request-list">
            {items.map((item) => (
              <article
                key={item.id}
                className="request-row"
                role="link"
                tabIndex={0}
                onClick={() => navigate(`/requests/${item.id}`)}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) {
                    return;
                  }
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    navigate(`/requests/${item.id}`);
                  }
                }}
              >
                <div className="request-row-top">
                  <div className="request-row-main">
                    <strong className="request-row-title">{`Request ${item.id}`}</strong>
                    <p>{item.progressMessage}</p>
                    <div className="request-row-meta">
                      <span>{item.resultsWritten} listings</span>
                      <span>{item.pagesCompleted} pages</span>
                      <span>{new Date(item.createdAt).toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="request-row-controls">
                    <StatusPill status={item.status} />
                    <IconButton
                      title="Delete request"
                      tone="danger"
                      disabled={inProgressStatuses.has(item.status)}
                      onClick={(event) => {
                        event.stopPropagation();
                        removeRequest(item.id);
                      }}
                    >
                      <IconTrash />
                    </IconButton>
                  </div>
                </div>
                <a
                  href={item.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="request-row-url"
                  title={item.sourceUrl}
                  onClick={(event) => event.stopPropagation()}
                  >
                  {item.sourceUrl}
                </a>
              </article>
            ))}
          </div>
        </div>
      </section>
    </Shell>
  );
}

function RequestDetailPage() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const loader = React.useCallback(() => api(`/api/requests/${requestId}`), [requestId]);
  const { data, loading, error, reload } = usePolling(loader, true);
  const item = data?.item;

  async function trigger(path) {
    await api(path, { method: "POST" });
    await reload();
  }

  async function removeRequest() {
    if (inProgressStatuses.has(item.status)) {
      window.alert("This request is still running and cannot be removed yet.");
      return;
    }
    if (!window.confirm("Remove this request and its stored files?")) {
      return;
    }
    try {
      await api(`/api/requests/${requestId}`, { method: "DELETE" });
      navigate("/");
    } catch (removeError) {
      window.alert(removeError.message);
    }
  }

  if (loading && !item) {
    return (
      <Shell title="Request details">
        <p className="muted">Loading request...</p>
      </Shell>
    );
  }

  if (error && !item) {
    return (
      <Shell title="Request details">
        <p className="error-text">{error.message}</p>
      </Shell>
    );
  }

  return (
    <Shell title="Request details">
      <Breadcrumbs
        items={[
          { label: "Requests", to: "/" },
          { label: `Request ${item.id}` },
        ]}
      />

      <section className="panel">
        <div className="detail-head">
          <div>
            <p className="muted">Source link</p>
            <a href={item.sourceUrl} target="_blank" rel="noreferrer" className="link-break">
              {item.sourceUrl}
            </a>
          </div>
          <div className="request-row-controls">
            <StatusPill status={item.status} />
            <IconButton title="Delete request" tone="danger" disabled={inProgressStatuses.has(item.status)} onClick={removeRequest}>
              <IconTrash />
            </IconButton>
          </div>
        </div>

        <div className="metric-grid">
          <Metric label="Pages completed" value={item.pagesCompleted} />
          <Metric label="Listings written" value={item.resultsWritten} />
          <Metric label="Results" value={item.resultsReady ? "Ready" : "Not ready"} />
          <Metric label="Excel" value={item.excelReady ? "Ready" : "Pending"} />
        </div>

        <div className="detail-actions">
          <button onClick={() => trigger(`/api/requests/${item.id}/resume`)} disabled={item.status === "running" || item.status === "pending" || item.status === "categorizing"}>
            Resume and gather new
          </button>
          <button className="button-secondary" onClick={() => trigger(`/api/requests/${item.id}/redo`)} disabled={item.status === "running" || item.status === "pending" || item.status === "categorizing"}>
            Redo from scratch
          </button>
          <a
            className={`button-link ${!item.excelReady ? "button-disabled" : ""}`}
            href={item.excelReady ? `/api/requests/${item.id}/excel` : undefined}
          >
            Download Excel
          </a>
          <Link
            className={`button-link ${!item.resultsReady ? "button-disabled" : ""}`}
            to={item.resultsReady ? `/requests/${item.id}/results` : "#"}
          >
            Open results
          </Link>
        </div>

        <p className="progress-box">{item.progressMessage}</p>
        {item.error ? <p className="error-text">{item.error}</p> : null}
      </section>
    </Shell>
  );
}

function LocationModal({ preview, onClose }) {
  const [coords, setCoords] = React.useState(null);
  const [geoError, setGeoError] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [userCoords, setUserCoords] = React.useState(null);

  React.useEffect(() => {
    if (!preview) {
      return undefined;
    }

    const controller = new AbortController();
    let active = true;

    async function lookupLocation() {
      setLoading(true);
      setGeoError(null);
      setCoords(null);
      try {
        const payload = await api(`/api/geocode?query=${encodeURIComponent(preview.location)}`, {
          signal: controller.signal,
        });
        const item = payload.item;
        if (active && item?.lat !== undefined && item?.lat !== null && item?.lon !== undefined && item?.lon !== null) {
          setCoords(item);
        }
        if (active && !item) {
          setGeoError("Location not found on map.");
        }
      } catch (error) {
        if (active && error.name !== "AbortError") {
          setGeoError("Could not load map preview.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    lookupLocation();

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          if (active) {
            setUserCoords({
              lat: position.coords.latitude,
              lon: position.coords.longitude,
            });
          }
        },
        () => {
          if (active) {
            setUserCoords(null);
          }
        },
        { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
      );
    }

    return () => {
      active = false;
      controller.abort();
    };
  }, [preview]);

  React.useEffect(() => {
    if (!preview) {
      return undefined;
    }

    function onKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [preview, onClose]);

  if (!preview) {
    return null;
  }

  const distanceKm =
    coords && userCoords ? haversineKm(userCoords, coords) : null;
  const googleMapsUrl = buildGoogleMapsUrl(preview.location);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">Location preview</p>
            <h2>{preview.location}</h2>
            <p className="muted">{preview.title}</p>
          </div>
          <div className="modal-head-actions">
            <IconButton title="Open in Google Maps" href={googleMapsUrl} tone="secondary">
              <IconExternal />
            </IconButton>
            <IconButton title="Close preview" tone="secondary" onClick={onClose}>
              <IconClose />
            </IconButton>
          </div>
        </div>

        <div className="modal-meta">
          <span className="chip chip-place">
            <span className="chip-label">Maps</span>
            <span>{coords?.label || preview.location}</span>
          </span>
          <span className="chip chip-time">
            <span className="chip-label">Distance</span>
            <span>{distanceKm !== null ? `~${distanceKm.toFixed(1)} km from you` : "Allow location to estimate distance"}</span>
          </span>
        </div>

        {loading ? <p className="progress-box">Loading map preview...</p> : null}
        {geoError ? <p className="error-text">{geoError}</p> : null}
        {coords ? (
          <iframe
            className="map-frame"
            title={`Map for ${preview.location}`}
            src={buildOsmEmbedUrl(coords.lat, coords.lon)}
            loading="lazy"
          />
        ) : null}

        <p className="muted modal-footnote">
          Distance is an approximate straight-line estimate from your browser location.
        </p>
      </div>
    </div>
  );
}

function DataPairs({ entries }) {
  return (
    <div className="report-pairs">
      {entries.map((entry) => (
        <div key={entry.label} className="report-pair">
          <span>{entry.label}</span>
          <strong>{formatValue(entry.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function DataTree({ label, value }) {
  if (value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) {
    return null;
  }

  if (Array.isArray(value)) {
    const scalarValues = value.every((item) => item === null || ["string", "number", "boolean"].includes(typeof item));
    if (scalarValues) {
      return (
        <div className="report-tree-block">
          <span className="report-tree-label">{label}</span>
          <div className="report-tree-value">{formatValue(value)}</div>
        </div>
      );
    }
    return (
      <div className="report-tree-block">
        <span className="report-tree-label">{label}</span>
        <div className="report-tree-nested-list">
          {value.map((item, index) => (
            <DataTree key={`${label}-${index}`} label={`${label} ${index + 1}`} value={item} />
          ))}
        </div>
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value).filter(([, child]) => child !== null && child !== undefined && child !== "");
    if (entries.length === 0) {
      return null;
    }
    const scalarEntries = entries.filter(([, child]) => child === null || ["string", "number", "boolean"].includes(typeof child));
    const nestedEntries = entries.filter(([, child]) => !(child === null || ["string", "number", "boolean"].includes(typeof child)));
    return (
      <div className="report-tree-block">
        <span className="report-tree-label">{label}</span>
        {scalarEntries.length ? (
          <DataPairs
            entries={scalarEntries.map(([childKey, childValue]) => ({
              label: formatFieldLabel(childKey),
              value: childValue,
            }))}
          />
        ) : null}
        {nestedEntries.length ? (
          <div className="report-tree-nested-list">
            {nestedEntries.map(([childKey, childValue]) => (
              <DataTree key={`${label}-${childKey}`} label={formatFieldLabel(childKey)} value={childValue} />
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="report-tree-block">
      <span className="report-tree-label">{label}</span>
      <div className="report-tree-value">{formatValue(value)}</div>
    </div>
  );
}

function VehicleReportModal({ state, onClose, onRegenerate }) {
  if (!state) {
    return null;
  }

  const { item, loading, regenerating, error, data } = state;
  const identity = data?.identity || {};
  const summary = data?.summary || {};
  const report = data?.report || {};
  const retrievedAt = data?.retrievedAt ? new Date(data.retrievedAt).toLocaleString() : null;
  const summaryEntries = [
    { label: "VIN", value: identity.vin },
    { label: "Registration", value: identity.registrationNumber },
    { label: "First registration", value: identity.firstRegistrationDate },
    { label: "Make", value: summary.make },
    { label: "Model", value: summary.model },
    { label: "Variant", value: summary.variant },
    { label: "Model year", value: summary.modelYear },
    { label: "Fuel", value: summary.fuelType },
    { label: "Engine capacity", value: summary.engineCapacity },
    { label: "Engine power", value: summary.enginePower },
    { label: "Body type", value: summary.bodyType },
    { label: "Color", value: summary.color },
    { label: "Owners", value: summary.ownersCount },
    { label: "Co-owners", value: summary.coOwnersCount },
    { label: "Last ownership change", value: summary.lastOwnershipChange },
  ].filter((entry) => entry.value !== null && entry.value !== undefined && entry.value !== "");

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel modal-panel-report" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">Vehicle report</p>
            <h2>{item.title}</h2>
            <p className="muted">{item.location || "Location unavailable"}</p>
          </div>
          <div className="modal-head-actions">
            <IconButton title="Open listing" href={item.url} tone="secondary">
              <IconExternal />
            </IconButton>
            <IconButton title="Regenerate report" tone="secondary" onClick={onRegenerate} disabled={loading || regenerating}>
              <IconRefresh />
            </IconButton>
            <IconButton title="Close report" tone="secondary" onClick={onClose}>
              <IconClose />
            </IconButton>
          </div>
        </div>

        <div className="modal-meta">
          <span className="chip chip-place">
            <span className="chip-label">Status</span>
            <span>{data ? "Cached report ready" : loading ? "Fetching report" : "Waiting"}</span>
          </span>
          <span className="chip chip-time">
            <span className="chip-label">Retrieved</span>
            <span>{retrievedAt || "Not retrieved yet"}</span>
          </span>
        </div>

        {loading ? <p className="progress-box">Fetching listing identity and vehicle history sources...</p> : null}
        {regenerating ? <p className="progress-box">Refreshing cached report...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {data ? (
          <div className="report-layout">
            <section className="report-section">
              <h3>Summary</h3>
              <DataPairs entries={summaryEntries} />
            </section>

            <section className="report-section">
              <h3>Source status</h3>
              <DataPairs
                entries={[
                  { label: "Historia Pojazdu API", value: report.api_version || "—" },
                  { label: "AutoDNA payload", value: summary.autodnaAvailable ? "Available" : summary.autodnaUnavailable ? "Unavailable" : "Empty" },
                  { label: "Carfax payload", value: summary.carfaxAvailable ? "Available" : summary.carfaxUnavailable ? "Unavailable" : "Empty" },
                  { label: "Advert id", value: identity.advertId },
                ]}
              />
            </section>

            <details className="report-details" open>
              <summary>Technical data</summary>
              <DataTree label="Technical data" value={report.technical_data} />
            </details>

            <details className="report-details">
              <summary>AutoDNA</summary>
              <DataTree label="AutoDNA" value={report.autodna_data} />
            </details>

            <details className="report-details">
              <summary>Carfax</summary>
              <DataTree label="Carfax" value={report.carfax_data} />
            </details>
            <details className="report-details">
              <summary>Timeline</summary>
              <DataTree label="Timeline" value={report.timeline_data} />
            </details>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ListingCard({ item, assignableCategories, categoryBusy, onAssignCategories, onCreateCategory, onOpenLocation, onOpenReport, distanceLabel }) {
  const [categoryPickerOpen, setCategoryPickerOpen] = React.useState(false);
  const createdAt = item.createdAt ? new Date(item.createdAt).toLocaleString() : "—";
  const reportStatus = item.vehicleReport?.status;
  const reportStateTitle = reportStatus === "success"
    ? `Report fetched ${item.vehicleReport?.retrievedAt ? new Date(item.vehicleReport.retrievedAt).toLocaleString() : ""}`.trim()
    : reportStatus === "failed"
      ? item.vehicleReport?.lastAttemptAt
        ? `Previous fetch failed ${new Date(item.vehicleReport.lastAttemptAt).toLocaleString()}`
        : "Previous fetch failed"
      : null;
  const specs = [
    ...(item.category === "Price evaluation out of range" && item.dataVerified === true
      ? [{ label: "Status", value: "Verified data", tone: "verified" }]
      : []),
    { label: "Price eval", value: item.priceEvaluation || "No price evaluation", tone: "price" },
    { label: "Engine", value: item.engineCapacity || "No engine capacity", tone: "engine" },
    { label: "Power", value: item.enginePower || "No power", tone: "engine" },
    { label: "Year", value: item.year || "No year", tone: "year" },
    { label: "Mileage", value: item.mileage || "No mileage", tone: "mileage" },
    { label: "Fuel", value: item.fuelType || "No fuel type", tone: "drive" },
    { label: "Gearbox", value: item.transmission || "No transmission", tone: "drive" },
    { label: "Created", value: createdAt, tone: "time" },
  ];

  return (
    <article className={categoryPickerOpen ? "listing-card listing-card-overlay-open" : "listing-card"}>
      <a
        href={item.url}
        target="_blank"
        rel="noreferrer"
        className="listing-card-anchor"
        aria-label={`Open listing: ${item.title || "listing"}`}
      />
      <div className="listing-card-body">
        <div className="listing-image-wrap">
          {item.imageUrl ? <img src={item.imageUrl} alt={item.title} className="listing-image" /> : <div className="listing-image placeholder" />}
        </div>
        <div className="listing-content">
          <div className="listing-topline">
            <h3>{item.title}</h3>
            <strong>{item.price ? `${item.price.toLocaleString("pl-PL")} ${item.priceCurrency}` : "—"}</strong>
          </div>
          <p className="muted">{item.shortDescription || "No short description."}</p>
          <div className="listing-action-row">
            <CategoryPicker
              item={item}
              categories={assignableCategories}
              busy={categoryBusy}
              onCommit={onAssignCategories}
              onCreateCategory={onCreateCategory}
              onOpenChange={setCategoryPickerOpen}
            />
            <button
              type="button"
              className="listing-report-button chip-interactive"
              title="Open vehicle report"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onOpenReport(item);
              }}
            >
              <IconReport />
              <span>Vehicle report</span>
              {reportStatus === "success" ? (
                <span className="listing-report-state listing-report-state-success" title={reportStateTitle}>
                  <IconCheckBadge />
                </span>
              ) : null}
              {reportStatus === "failed" ? (
                <span className="listing-report-state listing-report-state-failed" title={reportStateTitle}>
                  <IconXBadge />
                </span>
              ) : null}
            </button>
          </div>
          <div className="listing-place-row">
            {item.location ? (
              <button
                type="button"
                className="listing-place-button chip-interactive"
                title={`Preview ${item.location} on map`}
                onClick={() => onOpenLocation({ title: item.title, location: item.location })}
              >
                {item.location}
              </button>
            ) : (
              <span className="listing-place-text">No location</span>
            )}
            <span className="listing-distance-text">{distanceLabel}</span>
          </div>
          <div className="chip-row">
            {specs.map((spec) => (
              <span key={spec.label} className={`chip chip-${spec.tone}`}>
                <span className="chip-label">{spec.label}</span>
                <span>{spec.value}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}

function RequestResultsPage() {
  const { requestId } = useParams();
  const requestLoader = React.useCallback(() => api(`/api/requests/${requestId}`), [requestId]);
  const { data: requestData, loading: requestLoading } = usePolling(requestLoader, true);
  const request = requestData?.item;
  const [results, setResults] = React.useState(null);
  const [resultsError, setResultsError] = React.useState(null);
  const [activeCategory, setActiveCategory] = React.useState(systemCategoryOrder[0]);
  const [pageSize, setPageSize] = React.useState(pageSizeOptions[0]);
  const [currentPage, setCurrentPage] = React.useState(1);
  const [locationPreview, setLocationPreview] = React.useState(null);
  const [vehicleReportState, setVehicleReportState] = React.useState(null);
  const [geolocationState, setGeolocationState] = React.useState({ status: "idle", coords: null });
  const [locationCache, setLocationCache] = React.useState({});
  const [reloadToken, setReloadToken] = React.useState(0);
  const [categoryBusyByListing, setCategoryBusyByListing] = React.useState({});
  const vehicleReportRequestRef = React.useRef(0);
  const listTopRef = React.useRef(null);
  const previousPageRef = React.useRef(null);
  const paginationScrollRafRef = React.useRef(null);

  React.useEffect(() => {
    setPageSize(pageSizeOptions[0]);
    setCurrentPage(1);
    setReloadToken(0);
    previousPageRef.current = null;
    if (paginationScrollRafRef.current !== null) {
      window.cancelAnimationFrame(paginationScrollRafRef.current);
      paginationScrollRafRef.current = null;
    }
  }, [requestId]);

  const bumpResultsReload = React.useCallback(() => {
    setReloadToken((value) => value + 1);
  }, []);

  const promptCategoryName = React.useCallback((initialValue = "") => {
    const name = window.prompt("Category name", initialValue);
    if (name === null) {
      return null;
    }
    return name;
  }, []);

  const submitCategoryCreation = React.useCallback(async (initialValue = "") => {
    const name = promptCategoryName(initialValue);
    if (name === null) {
      return null;
    }
    const payload = await api(`/api/requests/${requestId}/categories`, {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    return payload.item;
  }, [promptCategoryName, requestId]);

  const createCategory = React.useCallback(async () => {
    try {
      const created = await submitCategoryCreation();
      if (!created) {
        return null;
      }
      setResults((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          categories: {
            ...current.categories,
            [created.key]: {
              label: created.label,
              count: 0,
              kind: created.kind,
              editable: created.editable,
              deletable: created.deletable,
            },
          },
          assignableCategories: [...(current.assignableCategories || []), created],
        };
      });
      setResultsError(null);
      return created;
    } catch (error) {
      setResultsError(error.message);
      return null;
    }
  }, [submitCategoryCreation]);

  const createCategoryTab = React.useCallback(async () => {
    const created = await createCategory();
    if (!created) {
      return;
    }
    setCurrentPage(1);
    setActiveCategory(created.key);
    bumpResultsReload();
  }, [bumpResultsReload, createCategory]);

  const renameActiveCategory = React.useCallback(async () => {
    const activeMeta = results?.categories?.[activeCategory];
    if (!activeMeta?.editable) {
      return;
    }
    const name = promptCategoryName(activeMeta.label);
    if (name === null) {
      return;
    }
    try {
      await api(`/api/requests/${requestId}/categories/${encodeURIComponent(activeCategory)}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      bumpResultsReload();
      setResultsError(null);
    } catch (error) {
      setResultsError(error.message);
    }
  }, [activeCategory, bumpResultsReload, promptCategoryName, requestId, results]);

  const deleteActiveCategory = React.useCallback(async () => {
    const activeMeta = results?.categories?.[activeCategory];
    if (!activeMeta?.deletable) {
      return;
    }
    if (!window.confirm(`Delete category "${activeMeta.label}"?`)) {
      return;
    }
    try {
      await api(`/api/requests/${requestId}/categories/${encodeURIComponent(activeCategory)}`, {
        method: "DELETE",
      });
      setActiveCategory(systemCategoryOrder[0]);
      setCurrentPage(1);
      bumpResultsReload();
      setResultsError(null);
    } catch (error) {
      setResultsError(error.message);
    }
  }, [activeCategory, bumpResultsReload, requestId, results]);

  const assignSavedCategories = React.useCallback(async (item, categoryKeys) => {
    setCategoryBusyByListing((current) => ({ ...current, [item.id]: true }));
    try {
      await api(`/api/requests/${requestId}/listings/${item.id}/categories`, {
        method: "PUT",
        body: JSON.stringify({ categoryIds: categoryKeys }),
      });
      setResultsError(null);
      bumpResultsReload();
    } catch (error) {
      setResultsError(error.message);
    } finally {
      setCategoryBusyByListing((current) => ({ ...current, [item.id]: false }));
    }
  }, [bumpResultsReload, requestId]);

  const openVehicleReport = React.useCallback(async (item) => {
    const requestToken = vehicleReportRequestRef.current + 1;
    vehicleReportRequestRef.current = requestToken;
    setVehicleReportState({ item, loading: true, regenerating: false, error: null, data: null });
    try {
      const payload = await api(`/api/requests/${requestId}/listings/${item.id}/vehicle-report`);
      if (vehicleReportRequestRef.current !== requestToken) {
        return;
      }
      setVehicleReportState({ item, loading: false, regenerating: false, error: null, data: payload.item });
      setResults((current) => {
        if (!current) {
          return current;
        }
        const items = (current.items || []).map((candidate) =>
          candidate.id === item.id
            ? {
                ...candidate,
                vehicleReport: {
                  cached: true,
                  retrievedAt: payload.item.retrievedAt,
                  status: "success",
                  lastAttemptAt: payload.item.retrievedAt,
                  lastError: null,
                },
              }
            : candidate,
        );
        return { ...current, items };
      });
    } catch (error) {
      if (vehicleReportRequestRef.current !== requestToken) {
        return;
      }
      setVehicleReportState({ item, loading: false, regenerating: false, error: error.message, data: null });
      setResults((current) => {
        if (!current) {
          return current;
        }
        const items = (current.items || []).map((candidate) =>
          candidate.id === item.id
            ? {
                ...candidate,
                vehicleReport: {
                  cached: candidate.vehicleReport?.cached === true,
                  retrievedAt: candidate.vehicleReport?.retrievedAt || null,
                  status: "failed",
                  lastAttemptAt: new Date().toISOString(),
                  lastError: error.message,
                },
              }
            : candidate,
        );
        return { ...current, items };
      });
    }
  }, [requestId]);

  const regenerateVehicleReport = React.useCallback(async () => {
    if (!vehicleReportState?.item) {
      return;
    }
    const item = vehicleReportState.item;
    const requestToken = vehicleReportRequestRef.current + 1;
    vehicleReportRequestRef.current = requestToken;
    setVehicleReportState((current) => ({ ...current, regenerating: true, error: null }));
    try {
      const payload = await api(`/api/requests/${requestId}/listings/${item.id}/vehicle-report/regenerate`, { method: "POST" });
      if (vehicleReportRequestRef.current !== requestToken) {
        return;
      }
      setVehicleReportState({ item, loading: false, regenerating: false, error: null, data: payload.item });
      setResults((current) => {
        if (!current) {
          return current;
        }
        const items = (current.items || []).map((candidate) =>
          candidate.id === item.id
            ? {
                ...candidate,
                vehicleReport: {
                  cached: true,
                  retrievedAt: payload.item.retrievedAt,
                  status: "success",
                  lastAttemptAt: payload.item.retrievedAt,
                  lastError: null,
                },
              }
            : candidate,
        );
        return { ...current, items };
      });
    } catch (error) {
      if (vehicleReportRequestRef.current !== requestToken) {
        return;
      }
      setVehicleReportState((current) => ({ ...current, regenerating: false, error: error.message }));
      setResults((current) => {
        if (!current) {
          return current;
        }
        const items = (current.items || []).map((candidate) =>
          candidate.id === item.id
            ? {
                ...candidate,
                vehicleReport: {
                  cached: candidate.vehicleReport?.cached === true,
                  retrievedAt: candidate.vehicleReport?.retrievedAt || null,
                  status: "failed",
                  lastAttemptAt: new Date().toISOString(),
                  lastError: error.message,
                },
              }
            : candidate,
        );
        return { ...current, items };
      });
    }
  }, [requestId, vehicleReportState]);

  React.useEffect(() => {
    let active = true;

    async function loadResults() {
      try {
        const params = new URLSearchParams({
          category: activeCategory,
          page: String(currentPage),
          page_size: String(pageSize),
        });
        const payload = await api(`/api/requests/${requestId}/results?${params.toString()}`);
        if (active) {
          setResults(payload);
          setResultsError(null);
          if (payload.currentCategory && payload.currentCategory !== activeCategory) {
            setActiveCategory(payload.currentCategory);
          }
        }
      } catch (error) {
        if (active) {
          setResults(null);
          setResultsError(error.message);
        }
      }
    }

    loadResults();
    if (!request || !request.resultsReady) {
      const timer = window.setInterval(loadResults, 3000);
      return () => {
        active = false;
        window.clearInterval(timer);
      };
    }

    return () => {
      active = false;
    };
  }, [activeCategory, currentPage, pageSize, reloadToken, request, requestId]);

  const categoryMap = results?.categories || {};
  const categoryEntries = Object.entries(categoryMap);
  const assignableCategories = results?.assignableCategories || [];
  const currentItems = results?.items || [];
  const totalPages = results?.pagination?.totalPages || 1;
  const safePage = results?.pagination?.page || 1;
  const pageNumbers = buildPageItems(safePage, totalPages);

  React.useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  React.useEffect(() => {
    if (previousPageRef.current === null) {
      previousPageRef.current = safePage;
      return;
    }
    if (previousPageRef.current !== safePage) {
      if (paginationScrollRafRef.current !== null) {
        window.cancelAnimationFrame(paginationScrollRafRef.current);
      }
      paginationScrollRafRef.current = window.requestAnimationFrame(() => {
        paginationScrollRafRef.current = null;
        const top = listTopRef.current?.getBoundingClientRect?.().top;
        if (typeof top !== "number") {
          return;
        }
        const targetTop = Math.max(0, top + window.scrollY - 16);
        scrollWindowToPosition(targetTop);
      });
      previousPageRef.current = safePage;
    }
    return () => {
      if (paginationScrollRafRef.current !== null) {
        window.cancelAnimationFrame(paginationScrollRafRef.current);
        paginationScrollRafRef.current = null;
      }
    };
  }, [safePage]);

  React.useEffect(() => {
    if (!results || geolocationState.status !== "idle") {
      return;
    }
    if (!navigator.geolocation) {
      setGeolocationState({ status: "unavailable", coords: null });
      return;
    }

    setGeolocationState({ status: "loading", coords: null });
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGeolocationState({
          status: "ready",
          coords: {
            lat: position.coords.latitude,
            lon: position.coords.longitude,
          },
        });
      },
      (error) => {
        setGeolocationState({
          status: error?.code === 1 ? "denied" : "unavailable",
          coords: null,
        });
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
    );
  }, [results, geolocationState.status]);

  React.useEffect(() => {
    if (!geolocationState.coords) {
      return;
    }

    const uniqueLocations = [...new Set(currentItems.map((item) => item.location).filter(Boolean))];
    const now = Date.now();
    const missingLocations = uniqueLocations.filter((location) => {
      const entry = locationCache[location];
      if (!entry) {
        return true;
      }
      return entry.status === "error" && (entry.retryAt || 0) <= now;
    });
    if (missingLocations.length === 0) {
      return;
    }

    setLocationCache((current) => ({
      ...current,
      ...Object.fromEntries(missingLocations.map((location) => [location, { status: "loading" }])),
    }));

    api("/api/geocode/batch", {
      method: "POST",
      body: JSON.stringify({ queries: missingLocations }),
    })
      .then((payload) => {
        setLocationCache((current) => ({
          ...current,
          ...Object.fromEntries(
            missingLocations.map((location) => {
              const item = payload.items?.[location];
              return [
                location,
                item
                  ? { status: "ready", coords: { lat: item.lat, lon: item.lon } }
                  : { status: "error", retryAt: Date.now() + 15000 },
              ];
            }),
          ),
        }));
      })
      .catch(() => {
        setLocationCache((current) => ({
          ...current,
          ...Object.fromEntries(
            missingLocations.map((location) => [location, { status: "error", retryAt: Date.now() + 15000 }]),
          ),
        }));
      });
  }, [currentItems, geolocationState.coords, locationCache]);

  return (
    <Shell title="Categorized results">
      <Breadcrumbs
        items={[
          { label: "Requests", to: "/" },
          request ? { label: `Request ${request.id}`, to: `/requests/${request.id}` } : { label: "Request" },
          { label: "Results" },
        ]}
      />

      <section className="panel">
        {requestLoading ? <p className="muted">Loading request...</p> : null}
        {request && !request.resultsReady ? (
          <>
            <p className="progress-box">{request.progressMessage}</p>
            <p className="muted">Results stay hidden until categorization finishes.</p>
          </>
        ) : null}
        {resultsError && request?.resultsReady ? <p className="error-text">{resultsError}</p> : null}
        {results ? (
          <>
            <div className="results-head">
              <div>
                <h2>{results.totalCount} listings</h2>
                <p className="muted">Generated {new Date(results.generatedAt).toLocaleString()}</p>
              </div>
              <div className="results-controls">
                <label className="page-size-control">
                  <span className="chip-label">Per page</span>
                  <select
                    value={pageSize}
                    onChange={(event) => {
                      setCurrentPage(1);
                      setPageSize(Number(event.target.value));
                    }}
                  >
                    {pageSizeOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            <div className="tab-row">
              {categoryEntries.map(([categoryKey, category]) => (
                <button
                  key={categoryKey}
                  className={categoryKey === activeCategory ? "tab active" : "tab"}
                  onClick={() => {
                    setCurrentPage(1);
                    setActiveCategory(categoryKey);
                  }}
                >
                  {category.kind === "saved" && category.label === "Favorites" ? <IconStar /> : null}
                  {category.label}
                  <span>{category.count || 0}</span>
                </button>
              ))}
              <div className="tab-row-actions">
                <IconButton title="Add category" tone="secondary" onClick={() => void createCategoryTab()}>
                  <IconPlus />
                </IconButton>
                {categoryMap[activeCategory]?.editable ? (
                  <IconButton title="Rename category" tone="secondary" onClick={renameActiveCategory}>
                    <IconEdit />
                  </IconButton>
                ) : null}
                {categoryMap[activeCategory]?.deletable ? (
                  <IconButton title="Delete category" tone="danger" onClick={deleteActiveCategory}>
                    <IconTrash />
                  </IconButton>
                ) : null}
              </div>
            </div>
            <div ref={listTopRef} className="results-list-top" />
            <div className="listing-grid">
              {currentItems.length === 0 ? <p className="muted">No listings in this category.</p> : null}
              {currentItems.map((item) => (
                <ListingCard
                  key={item.id}
                  item={item}
                  assignableCategories={assignableCategories}
                  categoryBusy={Boolean(categoryBusyByListing[item.id])}
                  onAssignCategories={assignSavedCategories}
                  onCreateCategory={createCategory}
                  onOpenLocation={setLocationPreview}
                  onOpenReport={openVehicleReport}
                  distanceLabel={formatDistanceChip(item.location, geolocationState, locationCache[item.location])}
                />
              ))}
            </div>
            {currentItems.length > 0 ? (
              <div className="results-footer">
                <div className="pagination">
                  <button
                    type="button"
                    className="pagination-button pagination-button-icon"
                    disabled={safePage === 1}
                    onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                    aria-label="Previous page"
                    title="Previous page"
                  >
                    <IconChevronLeft />
                  </button>
                  {pageNumbers.map((page, index) =>
                    page === "ellipsis" ? (
                      <span key={`ellipsis-${index}`} className="pagination-ellipsis">
                        …
                      </span>
                    ) : (
                      <button
                        key={page}
                        type="button"
                        className={page === safePage ? "pagination-button active" : "pagination-button"}
                        onClick={() => setCurrentPage(page)}
                      >
                        {page}
                      </button>
                    ),
                  )}
                  <button
                    type="button"
                    className="pagination-button pagination-button-icon"
                    disabled={safePage === totalPages}
                    onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                    aria-label="Next page"
                    title="Next page"
                  >
                    <IconChevronRight />
                  </button>
                </div>
                <p className="muted">{`Showing ${Math.min(results.pagination.totalItems, (safePage - 1) * pageSize + 1)}-${Math.min(results.pagination.totalItems, safePage * pageSize)} of ${results.pagination.totalItems}`}</p>
              </div>
            ) : null}
          </>
        ) : null}
      </section>
      <LocationModal
        key={locationPreview ? `${locationPreview.title}-${locationPreview.location}` : "no-location-preview"}
        preview={locationPreview}
        onClose={() => setLocationPreview(null)}
      />
      <VehicleReportModal
        state={vehicleReportState}
        onClose={() => {
          vehicleReportRequestRef.current += 1;
          setVehicleReportState(null);
        }}
        onRegenerate={regenerateVehicleReport}
      />
    </Shell>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RequestListPage />} />
        <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        <Route path="/requests/:requestId/results" element={<RequestResultsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
