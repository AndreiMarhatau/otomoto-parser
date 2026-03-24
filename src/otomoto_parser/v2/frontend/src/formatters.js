export function formatFieldLabel(key) {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^./, (char) => char.toUpperCase());
}

export function formatValue(value) {
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

export function normalizeLookupText(value) {
  return String(value || "").toUpperCase().replace(/\s+/g, "");
}

export function buildVehicleReportMeta(data, fallbackError = null) {
  const status = data?.report ? "success" : data?.status || (fallbackError ? "failed" : null);
  return {
    cached: Boolean(data?.report || (data?.summary && data?.identity)),
    retrievedAt: data?.retrievedAt || null,
    status,
    lastAttemptAt: data?.lastAttemptAt || data?.retrievedAt || null,
    lastError: fallbackError || data?.error || null,
    progressMessage: data?.progressMessage || null,
    lookup: data?.lookup || null,
    lookupOptions: data?.lookupOptions || null,
  };
}
