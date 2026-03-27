import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "./api";
import { inProgressStatuses } from "./constants";
import { IconTrash } from "./icons";
import { Breadcrumbs, IconButton, Metric, Shell, StatusPill } from "./layout";
import { usePolling } from "./use-polling";

export function RequestDetailPage() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, reload } = usePolling(() => api(`/api/requests/${requestId}`), true, `/api/requests/${requestId}`);
  const item = data?.item;

  async function trigger(path) {
    await api(path, { method: "POST" });
    await reload();
  }

  async function removeRequest() {
    if (inProgressStatuses.has(item.status)) return window.alert("This request is still running and cannot be removed yet.");
    if (!window.confirm("Remove this request and its stored files?")) return;
    try {
      await api(`/api/requests/${requestId}`, { method: "DELETE" });
      navigate("/");
    } catch (removeError) {
      window.alert(removeError.message);
    }
  }

  if (loading && !item) return <Shell title="Request details"><p className="muted">Loading request...</p></Shell>;
  if (error && !item) return <Shell title="Request details"><p className="error-text">{error.message}</p></Shell>;
  return (
    <Shell title="Request details" subtitle="Inspect the parser run, confirm outputs, and reopen the categorized review workspace when the batch is ready.">
      <Breadcrumbs items={[{ label: "Requests", to: "/" }, { label: `Request ${item.id}` }]} />
      <section className="panel">
        <div className="detail-head">
          <div className="detail-source"><p className="eyebrow">Source link</p><a href={item.sourceUrl} target="_blank" rel="noreferrer" className="link-break">{item.sourceUrl}</a></div>
          <div className="request-row-controls"><StatusPill status={item.status} /><IconButton title="Delete request" tone="danger" disabled={inProgressStatuses.has(item.status)} onClick={removeRequest}><IconTrash /></IconButton></div>
        </div>
        <div className="metric-grid"><Metric label="Pages completed" value={item.pagesCompleted} /><Metric label="Listings written" value={item.resultsWritten} /><Metric label="Results" value={item.resultsReady ? "Ready" : "Not ready"} /><Metric label="Excel" value={item.excelReady ? "Ready" : "Pending"} /></div>
        <div className="detail-actions">
          <button onClick={() => trigger(`/api/requests/${item.id}/resume`)} disabled={inProgressStatuses.has(item.status)}>Resume and gather new</button>
          <button className="button-secondary" onClick={() => trigger(`/api/requests/${item.id}/redo`)} disabled={inProgressStatuses.has(item.status)}>Redo from scratch</button>
          <a className={`button-link ${!item.excelReady ? "button-disabled" : ""}`} href={item.excelReady ? `/api/requests/${item.id}/excel` : undefined}>Download Excel</a>
          <Link className={`button-link ${!item.resultsReady ? "button-disabled" : ""}`} to={item.resultsReady ? `/requests/${item.id}/results` : "#"}>Open results</Link>
        </div>
        <p className="progress-box">{item.progressMessage}</p>{item.error ? <p className="error-text">{item.error}</p> : null}
      </section>
    </Shell>
  );
}
