import { normalizeLookupText } from "./formatters";

const EMPTY_LOOKUP_DEFAULTS = Object.freeze({
  registrationNumber: "",
  dateFrom: "",
  dateTo: "",
});

export { EMPTY_LOOKUP_DEFAULTS };

export function buildModalState(state) {
  const data = state?.data || null;
  return {
    item: state?.item || {},
    busyFlags: buildBusyFlags(state),
    error: state?.error || null,
    data,
    identity: data?.identity || {},
    summary: data?.summary || {},
    report: data?.report || {},
    retrievedAt: data?.retrievedAt ? new Date(data.retrievedAt).toLocaleString() : null,
    lookupOptions: data?.lookupOptions || {},
    activeLookup: data?.lookup || {},
  };
}

export function buildLookupDefaults(activeLookup, lookupOptions, identity) {
  return {
    registrationNumber: normalizeLookupText(preferredLookupValue(activeLookup.registrationNumber, lookupOptions.registrationNumber, identity.registrationNumber)),
    dateFrom: preferredLookupValue(lookupOptions.dateRange?.from, activeLookup.dateRange?.from),
    dateTo: preferredLookupValue(lookupOptions.dateRange?.to, activeLookup.dateRange?.to),
  };
}

export function emptyLookupFormState() {
  return { stateId: null, registrationNumber: "", dateFrom: "", dateTo: "", defaultValues: EMPTY_LOOKUP_DEFAULTS, dirty: false };
}

export function syncLookupFormState(currentState, stateId, defaultValues) {
  if (!stateId) {
    return emptyLookupFormState();
  }
  if (currentState.stateId !== stateId) {
    return { stateId, ...defaultValues, defaultValues, dirty: false };
  }
  if (currentState.dirty || areLookupDefaultsEqual(currentState.defaultValues, defaultValues)) {
    return currentState;
  }
  return { ...currentState, ...defaultValues, defaultValues };
}

export function updateLookupFormState(currentState, updates) {
  const nextState = { ...currentState, ...updates };
  return { ...nextState, dirty: !areLookupDefaultsEqual(nextState, currentState.defaultValues) };
}

export function areLookupDefaultsEqual(left, right) {
  return left.registrationNumber === right.registrationNumber && left.dateFrom === right.dateFrom && left.dateTo === right.dateTo;
}

export function buildProgressMessage(data, busyFlags) {
  if (busyFlags.loading) return "Fetching listing identity and vehicle history sources...";
  if (busyFlags.regenerating) return "Refreshing cached report...";
  if (busyFlags.cancellingLookup) return "Cancelling lookup...";
  if (!["running", "cancelling"].includes(data?.status)) return null;
  return data.progressMessage || (data?.status === "cancelling" ? "Cancelling vehicle history report lookup..." : "Searching vehicle history report...");
}

export function shouldShowLookupForm(data) {
  const hasRetryLookupContext = Boolean(data?.lookupOptions || data?.lookup);
  return data && !data.report && (data.status === "needs_input" || data.status === "running" || data.status === "cancelling" || data.status === "cancelled" || (data.status === "failed" && hasRetryLookupContext));
}

export function buildSummaryEntries(identity, summary) {
  return [
    { label: "VIN", value: identity.vin }, { label: "Registration", value: identity.registrationNumber }, { label: "First registration", value: identity.firstRegistrationDate }, { label: "Make", value: summary.make }, { label: "Model", value: summary.model }, { label: "Variant", value: summary.variant }, { label: "Model year", value: summary.modelYear }, { label: "Fuel", value: summary.fuelType }, { label: "Engine capacity", value: summary.engineCapacity }, { label: "Engine power", value: summary.enginePower }, { label: "Body type", value: summary.bodyType }, { label: "Color", value: summary.color }, { label: "Owners", value: summary.ownersCount }, { label: "Co-owners", value: summary.coOwnersCount }, { label: "Last ownership change", value: summary.lastOwnershipChange },
  ].filter((entry) => entry.value !== null && entry.value !== undefined && entry.value !== "");
}

export function buildSourceStatusEntries(identity, report, summary) {
  return [
    { label: "Historia Pojazdu API", value: report.api_version || "—" },
    { label: "Advert id", value: identity.advertId || "—" },
    { label: "AutoDNA", value: providerAvailabilityLabel({ available: summary.autodnaAvailable, unavailable: summary.autodnaUnavailable, providerData: report.autodna_data }) },
    { label: "Carfax", value: providerAvailabilityLabel({ available: summary.carfaxAvailable, unavailable: summary.carfaxUnavailable, providerData: report.carfax_data }) },
  ];
}

export function statusLabel(data, loading) {
  if (data?.report) return "Cached report ready";
  if (data?.status === "running") return "Searching";
  if (data?.status === "cancelling") return "Cancelling";
  if (data?.status === "cancelled") return "Cancelled";
  if (data?.status === "needs_input") return "Needs input";
  return loading ? "Fetching report" : "Waiting";
}

function buildBusyFlags(state) {
  return {
    loading: state?.loading || false,
    regenerating: state?.regenerating || false,
    submittingLookup: state?.submittingLookup || false,
    cancellingLookup: state?.cancellingLookup || false,
  };
}

function preferredLookupValue(...values) {
  return values.find((value) => value) || "";
}

function providerAvailabilityLabel({ available, unavailable, providerData }) {
  if (available) return "Available";
  if (unavailable) return "Unavailable";
  if (hasProviderPayload(providerData)) return "Empty";
  return "No data";
}

function hasProviderPayload(providerData) {
  return Boolean(providerData) && typeof providerData === "object" && Object.keys(providerData).length > 0;
}
