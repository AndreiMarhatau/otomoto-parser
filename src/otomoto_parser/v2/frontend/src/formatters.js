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

export function describeSourceUrl(sourceUrl) {
  const value = typeof sourceUrl === "string" ? sourceUrl.trim() : "";
  if (!value) {
    return { label: "No source", displayValue: "No source URL", href: null, compactValue: "No source URL" };
  }
  try {
    const parsed = new URL(value);
    return {
      label: parsed.hostname || "External URL",
      displayValue: value,
      href: value,
      compactValue: compactSourceUrl(value),
    };
  } catch {
    if (value.startsWith("/") || value.startsWith("./") || value.startsWith("../")) {
      return { label: "Relative URL", displayValue: value, href: value, compactValue: compactSourceUrl(value) };
    }
    return { label: "Invalid URL", displayValue: value, href: null, compactValue: compactSourceUrl(value) };
  }
}

export function compactSourceUrl(value, maxLength = 44) {
  const normalized = String(value || "").trim();
  if (!normalized) return "No source URL";
  if (normalized.length <= maxLength) return normalized;
  const headLength = Math.max(16, Math.floor(maxLength * 0.52));
  const tailLength = Math.max(8, maxLength - headLength - 1);
  return `${normalized.slice(0, headLength)}…${normalized.slice(-tailLength)}`;
}
