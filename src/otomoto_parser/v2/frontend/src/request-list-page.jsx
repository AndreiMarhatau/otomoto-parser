import React from "react";
import { useNavigate } from "react-router-dom";

import { api } from "./api";
import { inProgressStatuses } from "./constants";
import { compactSourceUrl, describeSourceUrl } from "./formatters";
import { IconClose, IconPlus, IconRefresh, IconTrash } from "./icons";
import { IconButton, Shell, StatusPill } from "./layout";
import { usePolling } from "./use-polling";

export function RequestListPage() {
  const navigate = useNavigate();
  const openCreateButtonRef = React.useRef(null);
  const shouldRestoreFocusRef = React.useRef(false);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [url, setUrl] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState(null);
  const { data, loading, reload } = usePolling(() => api("/api/requests"), true, "/api/requests");
  const items = data?.items || [];

  React.useEffect(() => {
    if (createOpen || !shouldRestoreFocusRef.current) return;
    shouldRestoreFocusRef.current = false;
    const timer = window.setTimeout(() => {
      openCreateButtonRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [createOpen]);

  function openCreateDialog() {
    shouldRestoreFocusRef.current = false;
    setUrl("");
    setError(null);
    setCreateOpen(true);
  }

  function closeCreateDialog() {
    if (creating) return false;
    shouldRestoreFocusRef.current = true;
    setCreateOpen(false);
    setError(null);
    return true;
  }

  async function submit(event) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const payload = await api("/api/requests", { method: "POST", body: JSON.stringify({ url }) });
      shouldRestoreFocusRef.current = false;
      setCreateOpen(false);
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
    <Shell
      title="Requests"
      subtitle="Review saved parser runs and reopen the ones that matter. Creation now stays out of the history view."
      actions={<div className="page-header-actions-group"><button ref={openCreateButtonRef} type="button" onClick={openCreateDialog}><IconPlus /> New request</button><IconButton title="Refresh request list" tone="secondary" onClick={() => reload()}><IconRefresh /></IconButton></div>}
    >
      <section className="panel panel-list">
        <div className="section-heading section-heading-inline">
          <div>
            <p className="section-kicker">History</p>
            <h2>{items.length ? `${items.length} saved request${items.length === 1 ? "" : "s"}` : "History"}</h2>
          </div>
          <p className="muted">Runs stay here with their latest parser state and outputs.</p>
        </div>
        {loading ? <p className="muted">Loading requests...</p> : null}
        {!loading && items.length === 0 ? <div className="empty-state empty-state-ruled"><strong>No requests yet.</strong><p className="muted">Use the rounded + action to start the first parser run.</p></div> : null}
        <div className="request-list request-list-compact">{items.map((item) => <RequestRow key={item.id} item={item} navigate={navigate} onRemove={removeRequest} />)}</div>
      </section>
      {createOpen ? <RequestCreateDialog url={url} setUrl={setUrl} creating={creating} error={error} onSubmit={submit} onClose={closeCreateDialog} /> : null}
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
          <div className="request-row-meta request-row-meta-compact"><span>{item.resultsWritten} listings</span><span>{item.pagesCompleted} pages</span><span>{new Date(item.createdAt).toLocaleString()}</span></div>
        </div>
        <div className="request-row-controls">
          <StatusPill status={item.status} />
          <IconButton title="Delete request" tone="danger" disabled={inProgressStatuses.has(item.status)} onClick={(event) => { event.stopPropagation(); onRemove(item.id); }}><IconTrash /></IconButton>
        </div>
      </div>
      {sourceMeta.href ? (
        <a href={sourceMeta.href} target="_blank" rel="noreferrer" className="request-row-url" title={sourceMeta.displayValue} aria-label={sourceMeta.displayValue} onClick={(event) => event.stopPropagation()}>{compactSourceUrl(sourceMeta.displayValue, 56)}</a>
      ) : (
        <span className="request-row-url" title={sourceMeta.displayValue}>{compactSourceUrl(sourceMeta.displayValue, 56)}</span>
      )}
    </article>
  );
}

function RequestCreateDialog({ url, setUrl, creating, error, onSubmit, onClose }) {
  const titleId = React.useId();
  const descriptionId = React.useId();
  const dialogRef = React.useRef(null);
  const textareaRef = React.useRef(null);

  React.useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  React.useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        const closed = onClose();
        if (closed) event.preventDefault();
        return;
      }
      if (event.key !== "Tab") return;
      const focusableElements = getFocusableElements(dialogRef.current);
      if (!focusableElements.length) {
        event.preventDefault();
        return;
      }
      const activeElement = document.activeElement;
      const activeIndex = focusableElements.indexOf(activeElement);
      event.preventDefault();
      if (event.shiftKey) {
        const previousIndex = activeIndex <= 0 ? focusableElements.length - 1 : activeIndex - 1;
        focusableElements[previousIndex]?.focus();
        return;
      }
      const nextIndex = activeIndex === -1 || activeIndex === focusableElements.length - 1 ? 0 : activeIndex + 1;
      focusableElements[nextIndex]?.focus();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} className="modal-panel modal-panel-compact" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId} onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">New request</p>
            <h2 id={titleId}>Create request</h2>
            <p id={descriptionId} className="muted">Paste an Otomoto search URL. Parsing starts immediately and the run is added to history.</p>
          </div>
          <IconButton title="Close dialog" tone="secondary" onClick={onClose}><IconClose /></IconButton>
        </div>
        <form className="request-form request-create-form" onSubmit={onSubmit}>
          <textarea ref={textareaRef} value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.otomoto.pl/osobowe/..." rows={4} required />
          <div className="form-actions form-actions-compact">
            <button type="submit" disabled={creating}>{creating ? "Creating..." : "Create request"}</button>
            <button type="button" className="button-secondary" onClick={onClose} disabled={creating}>Cancel</button>
          </div>
          {error ? <p className="error-text">{error}</p> : null}
        </form>
      </div>
    </div>
  );
}

function handleRowKeyDown(event, requestId, navigate) {
  if (event.target !== event.currentTarget) return;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    navigate(`/requests/${requestId}`);
  }
}

function getFocusableElements(container) {
  if (!container) return [];
  const selector = [
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'a[href]',
    '[tabindex]:not([tabindex="-1"])',
  ].join(", ");
  return Array.from(container.querySelectorAll(selector)).filter((element) => !element.hasAttribute("disabled"));
}
