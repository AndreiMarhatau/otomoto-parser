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
    <Shell title="Requests" subtitle="Create a parser run, monitor progress, and reopen previous searches without the decorative noise.">
      <section className="panel panel-grid">
        <div className="panel-block panel-block-emphasis">
          <div className="section-heading">
            <div>
              <p className="section-kicker">New request</p>
              <h2>Create request</h2>
            </div>
            <p className="muted">Paste an Otomoto search URL. Parsing starts immediately and the run stays available in history.</p>
          </div>
          <form className="request-form" onSubmit={submit}>
            <textarea value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.otomoto.pl/osobowe/..." rows={4} required />
            <div className="form-actions">
              <button type="submit" disabled={creating}>{creating ? "Creating..." : "Create request"}</button>
              <IconButton title="Refresh request list" tone="secondary" onClick={() => reload()}><IconRefresh /></IconButton>
            </div>
            {error ? <p className="error-text">{error}</p> : null}
          </form>
        </div>
        <div className="panel-block">
          <div className="section-heading section-heading-inline">
            <div>
              <p className="section-kicker">History</p>
              <h2>{items.length ? `${items.length} saved request${items.length === 1 ? "" : "s"}` : "History"}</h2>
            </div>
            <p className="muted">Runs stay here with their latest parser state and output links.</p>
          </div>
          {loading ? <p className="muted">Loading requests...</p> : null}
          {!loading && items.length === 0 ? <div className="empty-state"><strong>No requests yet.</strong><p className="muted">Create the first one from the form on the left.</p></div> : null}
          <div className="request-list">{items.map((item) => <RequestRow key={item.id} item={item} navigate={navigate} onRemove={removeRequest} />)}</div>
        </div>
      </section>
    </Shell>
  );
}

function RequestRow({ item, navigate, onRemove }) {
  const sourceMeta = describeSourceUrl(item.sourceUrl);
  return (
    <article key={item.id} className="request-row" role="link" tabIndex={0} onClick={() => navigate(`/requests/${item.id}`)} onKeyDown={(event) => handleRowKeyDown(event, item.id, navigate)}>
      <div className="request-row-top">
        <div className="request-row-main">
          <div className="request-row-heading">
            <strong className="request-row-title">{`Request ${item.id}`}</strong>
            <span className="request-row-source">{sourceMeta.label}</span>
          </div>
          <p>{item.progressMessage}</p>
          <div className="request-row-meta"><span>{item.resultsWritten} listings</span><span>{item.pagesCompleted} pages</span><span>{new Date(item.createdAt).toLocaleString()}</span></div>
        </div>
        <div className="request-row-controls">
          <StatusPill status={item.status} />
          <IconButton title="Delete request" tone="danger" disabled={inProgressStatuses.has(item.status)} onClick={(event) => { event.stopPropagation(); onRemove(item.id); }}><IconTrash /></IconButton>
        </div>
      </div>
      {sourceMeta.href ? (
        <a href={sourceMeta.href} target="_blank" rel="noreferrer" className="request-row-url" title={sourceMeta.displayValue} onClick={(event) => event.stopPropagation()}>{sourceMeta.displayValue}</a>
      ) : (
        <span className="request-row-url" title={sourceMeta.displayValue}>{sourceMeta.displayValue}</span>
      )}
    </article>
  );
}

function describeSourceUrl(sourceUrl) {
  const value = typeof sourceUrl === "string" ? sourceUrl.trim() : "";
  if (!value) {
    return { label: "No source", displayValue: "No source URL", href: null };
  }
  try {
    const parsed = new URL(value);
    return { label: parsed.hostname || "External URL", displayValue: value, href: value };
  } catch {
    if (value.startsWith("/") || value.startsWith("./") || value.startsWith("../")) {
      return { label: "Relative URL", displayValue: value, href: value };
    }
    return { label: "Invalid URL", displayValue: value, href: null };
  }
}

function handleRowKeyDown(event, requestId, navigate) {
  if (event.target !== event.currentTarget) return;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    navigate(`/requests/${requestId}`);
  }
}
