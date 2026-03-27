import React from "react";
import { useNavigate } from "react-router-dom";

import { api } from "./api";
import { inProgressStatuses } from "./constants";
import { IconRefresh, IconTrash } from "./icons";
import { IconButton, Shell, StatusPill } from "./layout";
import { usePolling } from "./use-polling";

export function RequestListPage() {
  const navigate = useNavigate();
  const [url, setUrl] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState(null);
  const { data, loading, reload } = usePolling(() => api("/api/requests"), true, "/api/requests");
  const items = data?.items || [];
  const readyCount = items.filter((item) => item.status === "ready").length;
  const activeCount = items.filter((item) => inProgressStatuses.has(item.status)).length;
  const listingCount = items.reduce((total, item) => total + (item.resultsWritten || 0), 0);

  async function submit(event) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const payload = await api("/api/requests", { method: "POST", body: JSON.stringify({ url }) });
      navigate(`/requests/${payload.item.id}`);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setCreating(false);
    }
  }

  async function removeRequest(requestId) {
    const request = items.find((item) => item.id === requestId);
    if (request && inProgressStatuses.has(request.status)) return window.alert("This request is still running and cannot be removed yet.");
    if (!window.confirm("Remove this request and its stored files?")) return;
    try {
      await api(`/api/requests/${requestId}`, { method: "DELETE" });
      await reload();
    } catch (removeError) {
      window.alert(removeError.message);
    }
  }

  return (
    <Shell title="Version 2 workspace" subtitle="Parse live Otomoto searches, triage newly fetched stock, and keep every run in a reviewable history.">
      <section className="hero-metrics">
        <MetricCard label="Requests in desk" value={items.length} tone="neutral" />
        <MetricCard label="Ready for review" value={readyCount} tone="positive" />
        <MetricCard label="Currently running" value={activeCount} tone="warning" />
        <MetricCard label="Listings captured" value={listingCount} tone="accent" />
      </section>
      <section className="panel panel-grid">
        <div className="panel-block">
          <div className="section-heading"><p className="eyebrow">Start a run</p><h2>Create request</h2><p className="muted">Paste an Otomoto search URL. The backend starts parsing immediately and keeps progress in history.</p></div>
          <form className="request-form" onSubmit={submit}>
            <textarea value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.otomoto.pl/osobowe/..." rows={5} required />
            <div className="form-actions">
              <button type="submit" disabled={creating}>{creating ? "Creating..." : "Create request"}</button>
              <IconButton title="Refresh request list" tone="secondary" onClick={() => reload()}><IconRefresh /></IconButton>
            </div>
            {error ? <p className="error-text">{error}</p> : null}
          </form>
        </div>
        <div className="panel-block">
          <div className="section-heading"><p className="eyebrow">Review queue</p><h2>History</h2><p className="muted">Each request keeps parser progress, result files, categorized output, and exports together.</p></div>
          {loading ? <p className="muted">Loading requests...</p> : null}{!loading && items.length === 0 ? <p className="muted">No requests yet.</p> : null}
          <div className="request-list">{items.map((item) => <RequestRow key={item.id} item={item} navigate={navigate} onRemove={removeRequest} />)}</div>
        </div>
      </section>
    </Shell>
  );
}

function MetricCard({ label, value, tone }) {
  return (
    <div className={`hero-metric hero-metric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RequestRow({ item, navigate, onRemove }) {
  return (
    <article key={item.id} className="request-row" role="link" tabIndex={0} onClick={() => navigate(`/requests/${item.id}`)} onKeyDown={(event) => handleRowKeyDown(event, item.id, navigate)}>
      <div className="request-row-top">
        <div className="request-row-main">
          <strong className="request-row-title">{`Request ${item.id}`}</strong>
          <p>{item.progressMessage}</p>
          <div className="request-row-meta"><span>{item.resultsWritten} listings</span><span>{item.pagesCompleted} pages</span><span>{new Date(item.createdAt).toLocaleString()}</span></div>
        </div>
        <div className="request-row-controls">
          <StatusPill status={item.status} />
          <IconButton title="Delete request" tone="danger" disabled={inProgressStatuses.has(item.status)} onClick={(event) => { event.stopPropagation(); onRemove(item.id); }}><IconTrash /></IconButton>
        </div>
      </div>
      <a href={item.sourceUrl} target="_blank" rel="noreferrer" className="request-row-url" title={item.sourceUrl} onClick={(event) => event.stopPropagation()}>{item.sourceUrl}</a>
    </article>
  );
}

function handleRowKeyDown(event, requestId, navigate) {
  if (event.target !== event.currentTarget) return;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    navigate(`/requests/${requestId}`);
  }
}
