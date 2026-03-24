import React from "react";

import { formatFieldLabel, formatValue } from "./formatters";

export function DataPairs({ entries }) {
  return <div className="report-pairs">{entries.map((entry) => <div className="report-pair" key={entry.label}><span>{entry.label}</span><strong>{formatValue(entry.value)}</strong></div>)}</div>;
}

export function DataTree({ label, value }) {
  if (value === null || value === undefined || value === "") {
    return <div className="report-tree-block"><span className="report-tree-label">{label}</span><div className="report-tree-value">—</div></div>;
  }
  if (Array.isArray(value)) {
    return <div className="report-tree-block"><span className="report-tree-label">{label}</span><div className="report-tree-array">{value.map((entry, index) => <DataTree key={`${label}-${index}`} label={`${label} ${index + 1}`} value={entry} />)}</div></div>;
  }
  if (typeof value === "object") {
    return <div className="report-tree-block"><span className="report-tree-label">{label}</span><div className="report-tree-grid">{Object.entries(value).map(([key, entry]) => <DataTree key={key} label={formatFieldLabel(key)} value={entry} />)}</div></div>;
  }
  return <div className="report-tree-block"><span className="report-tree-label">{label}</span><div className="report-tree-value">{formatValue(value)}</div></div>;
}
