import React from "react";
import { Link } from "react-router-dom";

export function scrollWindowToPosition(top) {
  window.scrollTo(0, top);
  if (document.scrollingElement) document.scrollingElement.scrollTop = top;
  document.documentElement.scrollTop = top;
  document.body.scrollTop = top;
}

export function buildPageItems(currentPage, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const normalized = [...new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1])]
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
  const items = [];
  for (const page of normalized) {
    const previous = items[items.length - 1];
    if (typeof previous === "number" && page - previous > 1) items.push("ellipsis");
    items.push(page);
  }
  return items;
}

export function IconButton({ title, onClick, href, disabled = false, tone = "default", children }) {
  const className = `icon-button icon-button-${tone}${disabled ? " icon-button-disabled" : ""}`;
  if (href) {
    return <a href={href} target="_blank" rel="noreferrer" className={className} title={title} aria-label={title}>{children}</a>;
  }
  return <button type="button" className={className} title={title} aria-label={title} onClick={onClick} disabled={disabled}>{children}</button>;
}

export function Shell({ title, subtitle, children }) {
  return (
    <div className="shell">
      <div className="shell-glow shell-glow-a" />
      <div className="shell-glow shell-glow-b" />
      <header className="shell-topbar">
        <div className="shell-brand">
          <p className="eyebrow">Otomoto Parser</p>
          <strong>Review workspace</strong>
        </div>
        <nav className="shell-nav" aria-label="Primary">
          <Link to="/" className="hero-link">All requests</Link>
          <Link to="/settings" className="hero-link">Settings</Link>
        </nav>
      </header>
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-badge">Inventory triage and reporting</span>
          <h1>{title}</h1>
          {subtitle ? <p className="hero-subtitle">{subtitle}</p> : null}
        </div>
        <aside className="hero-aside">
          <span>Workspace scope</span>
          <strong>Requests, categorization, distance context, and vehicle reports in one flow.</strong>
        </aside>
      </section>
      <main className="shell-content">{children}</main>
    </div>
  );
}

export function Breadcrumbs({ items }) {
  return <nav className="breadcrumbs" aria-label="Breadcrumbs">{items.map((item, index) => <React.Fragment key={item.label}>{index > 0 ? <span>/</span> : null}{item.to ? <Link to={item.to}>{item.label}</Link> : <span>{item.label}</span>}</React.Fragment>)}</nav>;
}

export function StatusPill({ status }) {
  return <span className={`status-pill status-${status}`}>{status}</span>;
}

export function Metric({ label, value }) {
  return <div className="metric"><span>{label}</span><strong>{value ?? "—"}</strong></div>;
}
