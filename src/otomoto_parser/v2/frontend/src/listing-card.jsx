import React from "react";

import { CategoryPicker } from "./category-picker";
import { IconCheckBadge, IconReport, IconXBadge } from "./icons";

export function ListingCard({ item, assignableCategories, categoryBusy, onAssignCategories, onCreateCategory, onOpenLocation, onOpenReport, distanceLabel }) {
  const [categoryPickerOpen, setCategoryPickerOpen] = React.useState(false);
  const createdAt = item.createdAt ? new Date(item.createdAt).toLocaleString() : "—";
  const reportStatus = item.vehicleReport?.status;
  const reportStateTitle = reportTitle(reportStatus, item.vehicleReport);
  const specs = listingSpecs(item, createdAt);
  return (
    <article className={categoryPickerOpen ? "listing-card listing-card-overlay-open" : "listing-card"}>
      <a href={item.url} target="_blank" rel="noreferrer" className="listing-card-anchor" aria-label={`Open listing: ${item.title || "listing"}`} />
      <div className="listing-card-body">
        <div className="listing-image-wrap">{item.imageUrl ? <img src={item.imageUrl} alt={item.title} className="listing-image" /> : <div className="listing-image placeholder" />}</div>
        <div className="listing-content">
          <div className="listing-topline"><h3>{item.title}</h3><strong>{item.price ? `${item.price.toLocaleString("pl-PL")} ${item.priceCurrency}` : "—"}</strong></div>
          <p className="muted">{item.shortDescription || "No short description."}</p>
          <ListingActions item={item} assignableCategories={assignableCategories} categoryBusy={categoryBusy} onAssignCategories={onAssignCategories} onCreateCategory={onCreateCategory} onOpenReport={onOpenReport} onOpenChange={setCategoryPickerOpen} reportStatus={reportStatus} reportStateTitle={reportStateTitle} />
          <div className="listing-place-row">
            {item.location ? <button type="button" className="listing-place-button chip-interactive" title={`Preview ${item.location} on map`} onClick={() => onOpenLocation({ title: item.title, location: item.location })}>{item.location}</button> : <span className="listing-place-text">No location</span>}
            <span className="listing-distance-text">{distanceLabel}</span>
          </div>
          <div className="chip-row">{specs.map((spec) => <span key={spec.label} className={`chip chip-${spec.tone}`}><span className="chip-label">{spec.label}</span><span>{spec.value}</span></span>)}</div>
        </div>
      </div>
    </article>
  );
}

function ListingActions({ item, assignableCategories, categoryBusy, onAssignCategories, onCreateCategory, onOpenReport, onOpenChange, reportStatus, reportStateTitle }) {
  return (
    <div className="listing-action-row">
      <CategoryPicker item={item} categories={assignableCategories} busy={categoryBusy} onCommit={onAssignCategories} onCreateCategory={onCreateCategory} onOpenChange={onOpenChange} />
      <button type="button" className="listing-report-button chip-interactive" title="Open vehicle report" onClick={(event) => { event.preventDefault(); event.stopPropagation(); onOpenReport(item); }}>
        <IconReport /><span>Vehicle report</span>{reportStatus === "success" ? <span className="listing-report-state listing-report-state-success" title={reportStateTitle}><IconCheckBadge /></span> : null}{reportStatus === "failed" ? <span className="listing-report-state listing-report-state-failed" title={reportStateTitle}><IconXBadge /></span> : null}
      </button>
    </div>
  );
}

function reportTitle(reportStatus, vehicleReport) {
  if (reportStatus === "success") {
    return `Report fetched ${vehicleReport?.retrievedAt ? new Date(vehicleReport.retrievedAt).toLocaleString() : ""}`.trim();
  }
  if (reportStatus === "failed") {
    return vehicleReport?.lastAttemptAt ? `Previous fetch failed ${new Date(vehicleReport.lastAttemptAt).toLocaleString()}` : "Previous fetch failed";
  }
  return null;
}

function listingSpecs(item, createdAt) {
  return [
    ...(item.category === "Price evaluation out of range" && item.dataVerified === true ? [{ label: "Status", value: "Verified data", tone: "verified" }] : []),
    { label: "Price eval", value: item.priceEvaluation || "No price evaluation", tone: "price" },
    { label: "Engine", value: item.engineCapacity || "No engine capacity", tone: "engine" },
    { label: "Power", value: item.enginePower || "No power", tone: "engine" },
    { label: "Year", value: item.year || "No year", tone: "year" },
    { label: "Mileage", value: item.mileage || "No mileage", tone: "mileage" },
    { label: "Fuel", value: item.fuelType || "No fuel type", tone: "drive" },
    { label: "Gearbox", value: item.transmission || "No transmission", tone: "drive" },
    { label: "Created", value: createdAt, tone: "time" },
  ];
}
