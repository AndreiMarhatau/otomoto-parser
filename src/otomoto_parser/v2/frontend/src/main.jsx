import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useNavigate, useParams } from "react-router-dom";
import "./styles.css";

const categoryOrder = [
  "Price evaluation out of range",
  "Data not verified",
  "Imported from US",
  "To be checked",
];

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
              <button type="button" className="button-secondary" onClick={() => reload()}>
                Refresh list
              </button>
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
              <Link key={item.id} to={`/requests/${item.id}`} className="request-row">
                <div className="request-row-top">
                  <strong>{item.sourceUrl}</strong>
                  <StatusPill status={item.status} />
                </div>
                <p>{item.progressMessage}</p>
                <div className="request-row-meta">
                  <span>{item.resultsWritten} listings</span>
                  <span>{item.pagesCompleted} pages</span>
                  <span>{new Date(item.createdAt).toLocaleString()}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </Shell>
  );
}

function RequestDetailPage() {
  const { requestId } = useParams();
  const loader = React.useCallback(() => api(`/api/requests/${requestId}`), [requestId]);
  const { data, loading, error, reload } = usePolling(loader, true);
  const item = data?.item;

  async function trigger(path) {
    await api(path, { method: "POST" });
    await reload();
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
          <StatusPill status={item.status} />
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

function ListingCard({ item }) {
  const createdAt = item.createdAt ? new Date(item.createdAt).toLocaleString() : "—";
  const specs = [
    { label: "Price eval", value: item.priceEvaluation || "No price evaluation", tone: "price" },
    { label: "Engine", value: item.engineCapacity || "No engine capacity", tone: "engine" },
    { label: "Power", value: item.enginePower || "No power", tone: "engine" },
    { label: "Year", value: item.year || "No year", tone: "year" },
    { label: "Mileage", value: item.mileage || "No mileage", tone: "mileage" },
    { label: "Fuel", value: item.fuelType || "No fuel type", tone: "drive" },
    { label: "Gearbox", value: item.transmission || "No transmission", tone: "drive" },
    { label: "Location", value: item.location || "No location", tone: "place" },
    { label: "Created", value: createdAt, tone: "time" },
  ];

  return (
    <a href={item.url} target="_blank" rel="noreferrer" className="listing-card">
      <div className="listing-image-wrap">
        {item.imageUrl ? <img src={item.imageUrl} alt={item.title} className="listing-image" /> : <div className="listing-image placeholder" />}
      </div>
      <div className="listing-content">
        <div className="listing-topline">
          <h3>{item.title}</h3>
          <strong>{item.price ? `${item.price.toLocaleString("pl-PL")} ${item.priceCurrency}` : "—"}</strong>
        </div>
        <p className="muted">{item.shortDescription || "No short description."}</p>
        <div className="chip-row">
          {specs.map((spec) => (
            <span key={spec.label} className={`chip chip-${spec.tone}`}>
              <span className="chip-label">{spec.label}</span>
              <span>{spec.value}</span>
            </span>
          ))}
        </div>
      </div>
    </a>
  );
}

function RequestResultsPage() {
  const { requestId } = useParams();
  const requestLoader = React.useCallback(() => api(`/api/requests/${requestId}`), [requestId]);
  const { data: requestData, loading: requestLoading } = usePolling(requestLoader, true);
  const request = requestData?.item;
  const [results, setResults] = React.useState(null);
  const [resultsError, setResultsError] = React.useState(null);
  const [activeCategory, setActiveCategory] = React.useState(categoryOrder[0]);

  React.useEffect(() => {
    let active = true;

    async function loadResults() {
      try {
        const payload = await api(`/api/requests/${requestId}/results`);
        if (active) {
          setResults(payload);
          setResultsError(null);
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
  }, [request, requestId]);

  const categoryMap = results?.categories || {};
  const currentItems = categoryMap[activeCategory]?.items || [];

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
            </div>
            <div className="tab-row">
              {categoryOrder.map((category) => (
                <button
                  key={category}
                  className={category === activeCategory ? "tab active" : "tab"}
                  onClick={() => setActiveCategory(category)}
                >
                  {category}
                  <span>{categoryMap[category]?.count || 0}</span>
                </button>
              ))}
            </div>
            <div className="listing-grid">
              {currentItems.length === 0 ? <p className="muted">No listings in this category.</p> : null}
              {currentItems.map((item) => (
                <ListingCard key={item.id} item={item} />
              ))}
            </div>
          </>
        ) : null}
      </section>
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
