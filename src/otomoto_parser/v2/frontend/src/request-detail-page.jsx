import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "./api";
import { inProgressStatuses } from "./constants";
import { compactSourceUrl, describeSourceUrl } from "./formatters";
import { IconExternal, IconTrash } from "./icons";
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

  if (loading && !item) return <Shell title="Request details" subtitle="Inspect parser progress and reopen outputs from a single request."><p className="muted">Loading request...</p></Shell>;
  if (error && !item) return <Shell title="Request details" subtitle="Inspect parser progress and reopen outputs from a single request."><p className="error-text">{error.message}</p></Shell>;
  const sourceMeta = describeSourceUrl(item.sourceUrl);
  return (
    <Shell title={`Request ${item.id}`} subtitle="Single request status with the minimum controls needed to rerun, inspect outputs, or remove stored data.">
      <Breadcrumbs items={[{ label: "Requests", to: "/" }, { label: "Details" }]} />
      <section className="panel">
        <div className="detail-head detail-head-simple detail-head-compact">
          <div className="detail-source">
            <p className="section-kicker">Source</p>
            <div className="detail-source-row detail-source-row-compact">
              {sourceMeta.href ? (
                <a href={sourceMeta.href} target="_blank" rel="noreferrer" className="detail-source-link" title={sourceMeta.displayValue} aria-label={sourceMeta.displayValue}>{compactSourceUrl(sourceMeta.displayValue, 64)}</a>
              ) : (
                <span className="detail-source-link" title={sourceMeta.displayValue}>{compactSourceUrl(sourceMeta.displayValue, 64)}</span>
              )}
              {sourceMeta.href ? <IconButton title="Open source URL" href={sourceMeta.href} tone="secondary"><IconExternal /></IconButton> : null}
            </div>
          </div>
          <div className="request-row-controls"><StatusPill status={item.status} /><IconButton title="Delete request" tone="danger" disabled={inProgressStatuses.has(item.status)} onClick={removeRequest}><IconTrash /></IconButton></div>
        </div>
        <div className="metric-grid metric-grid-compact"><Metric label="Pages completed" value={item.pagesCompleted} /><Metric label="Listings written" value={item.resultsWritten} /><Metric label="Results" value={item.resultsReady ? "Ready" : "Not ready"} /><Metric label="Excel export" value={item.excelReady ? "Ready" : "Pending"} /></div>
        <div className="detail-actions detail-actions-simple detail-actions-compact">
          <button onClick={() => trigger(`/api/requests/${item.id}/resume`)} disabled={inProgressStatuses.has(item.status)}>Resume and gather new</button>
          <button className="button-secondary" onClick={() => trigger(`/api/requests/${item.id}/redo`)} disabled={inProgressStatuses.has(item.status)}>Redo from scratch</button>
          <Link className={`button-link button-link-secondary ${!item.resultsReady ? "button-disabled" : ""}`} to={item.resultsReady ? `/requests/${item.id}/results` : "#"}>Results</Link>
          <a className={`button-link button-link-secondary ${!item.excelReady ? "button-disabled" : ""}`} href={item.excelReady ? `/api/requests/${item.id}/excel` : undefined}>Excel</a>
        </div>
        <p className="progress-box progress-box-simple">{item.progressMessage}</p>{item.error ? <p className="error-text">{item.error}</p> : null}
      </section>
    </Shell>
  );
}
