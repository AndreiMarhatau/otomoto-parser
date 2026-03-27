import React from "react";
import {
  Alert,
  Chip,
  Dialog,
  DialogContent,
  Divider,
  Stack,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";

import { normalizeLookupText } from "./formatters";
import { VehicleReportDialogHeader } from "./vehicle-report-dialog-header";
import { VehicleAnalysisSection, VehicleLookupSection, VehicleReportDetails } from "./vehicle-report-sections";

const EMPTY_LOOKUP_DEFAULTS = Object.freeze({
  registrationNumber: "",
  dateFrom: "",
  dateTo: "",
});

export function VehicleReportModal({ state, redFlagState, settings, onClose, onRegenerate, onLookup, onCancelLookup, onStartRedFlags, onCancelRedFlags }) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("md"));
  const modalState = buildModalState(state);
  const progressMessage = buildProgressMessage(modalState.data, modalState.busyFlags);
  const [formState, setFormState] = React.useState(() => emptyLookupFormState());
  const defaultLookupValues = React.useMemo(
    () => (state ? buildLookupDefaults(modalState.activeLookup, modalState.lookupOptions, modalState.identity) : EMPTY_LOOKUP_DEFAULTS),
    [modalState.activeLookup, modalState.identity, modalState.lookupOptions, state],
  );

  React.useEffect(() => {
    setFormState((current) => {
      if (!state) {
        return current.stateId === null && areLookupDefaultsEqual(current.defaultValues, EMPTY_LOOKUP_DEFAULTS) && !current.dirty
          ? current
          : emptyLookupFormState();
      }
      return syncLookupFormState(current, state.item.id, defaultLookupValues);
    });
  }, [defaultLookupValues, state]);

  if (!state) return null;
  const { item, busyFlags, error, data, identity, summary, report, retrievedAt, lookupOptions, activeLookup } = modalState;
  const showLookupForm = shouldShowLookupForm(data);
  const summaryEntries = buildSummaryEntries(identity, summary);
  const sourceStatusEntries = buildSourceStatusEntries(identity, report, summary);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="lg" fullScreen={fullScreen}>
      <VehicleReportDialogHeader item={item} busyFlags={busyFlags} status={data?.status} onClose={onClose} onRegenerate={onRegenerate} />
      <DialogContent dividers>
        <Stack spacing={2.25}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip label={statusLabel(data, busyFlags.loading)} />
            <Chip label={`Retrieved: ${retrievedAt || "Not retrieved yet"}`} />
          </Stack>
          {progressMessage ? <Alert severity="info">{progressMessage}</Alert> : null}
          {error ? <Alert severity="error">{error}</Alert> : null}
          {!error && data?.error ? <Alert severity="error">{data.error}</Alert> : null}
          <VehicleAnalysisSection analysisState={redFlagState} data={data} settings={settings} busyFlags={busyFlags} onStartRedFlags={onStartRedFlags} onCancelRedFlags={onCancelRedFlags} />
          {showLookupForm ? (
            <>
              <Divider />
              <VehicleLookupSection
                data={data}
                identity={identity}
                lookupOptions={lookupOptions}
                activeLookup={activeLookup}
                registrationNumber={formState.registrationNumber}
                dateFrom={formState.dateFrom}
                dateTo={formState.dateTo}
                setRegistrationNumber={(value) => setFormState((current) => updateLookupFormState(current, { registrationNumber: value }))}
                setDateFrom={(value) => setFormState((current) => updateLookupFormState(current, { dateFrom: value }))}
                setDateTo={(value) => setFormState((current) => updateLookupFormState(current, { dateTo: value }))}
                busyFlags={busyFlags}
                onLookup={onLookup}
                onCancelLookup={onCancelLookup}
              />
            </>
          ) : null}
          {data?.report ? (
            <>
              <Divider />
              <Typography variant="h6">View report</Typography>
              <VehicleReportDetails identity={identity} report={report} summary={summary} summaryEntries={summaryEntries} sourceStatusEntries={sourceStatusEntries} />
            </>
          ) : null}
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

function buildBusyFlags(state) {
  return {
    loading: state?.loading || false,
    regenerating: state?.regenerating || false,
    submittingLookup: state?.submittingLookup || false,
    cancellingLookup: state?.cancellingLookup || false,
  };
}

function buildModalState(state) {
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

function preferredLookupValue(...values) {
  return values.find((value) => value) || "";
}

function buildLookupDefaults(activeLookup, lookupOptions, identity) {
  return {
    registrationNumber: normalizeLookupText(preferredLookupValue(activeLookup.registrationNumber, lookupOptions.registrationNumber, identity.registrationNumber)),
    dateFrom: preferredLookupValue(lookupOptions.dateRange?.from, activeLookup.dateRange?.from),
    dateTo: preferredLookupValue(lookupOptions.dateRange?.to, activeLookup.dateRange?.to),
  };
}

function emptyLookupFormState() {
  return { stateId: null, registrationNumber: "", dateFrom: "", dateTo: "", defaultValues: EMPTY_LOOKUP_DEFAULTS, dirty: false };
}

function syncLookupFormState(currentState, stateId, defaultValues) {
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

function updateLookupFormState(currentState, updates) {
  const nextState = { ...currentState, ...updates };
  return { ...nextState, dirty: !areLookupDefaultsEqual(nextState, currentState.defaultValues) };
}

function areLookupDefaultsEqual(left, right) {
  return left.registrationNumber === right.registrationNumber && left.dateFrom === right.dateFrom && left.dateTo === right.dateTo;
}

function buildProgressMessage(data, busyFlags) {
  if (busyFlags.loading) return "Fetching listing identity and vehicle history sources...";
  if (busyFlags.regenerating) return "Refreshing cached report...";
  if (busyFlags.cancellingLookup) return "Cancelling lookup...";
  if (!["running", "cancelling"].includes(data?.status)) return null;
  return data.progressMessage || (data?.status === "cancelling" ? "Cancelling vehicle history report lookup..." : "Searching vehicle history report...");
}

function shouldShowLookupForm(data) {
  const hasRetryLookupContext = Boolean(data?.lookupOptions || data?.lookup);
  return data && !data.report && (data.status === "needs_input" || data.status === "running" || data.status === "cancelling" || data.status === "cancelled" || (data.status === "failed" && hasRetryLookupContext));
}

function buildSummaryEntries(identity, summary) {
  return [
    { label: "VIN", value: identity.vin }, { label: "Registration", value: identity.registrationNumber }, { label: "First registration", value: identity.firstRegistrationDate }, { label: "Make", value: summary.make }, { label: "Model", value: summary.model }, { label: "Variant", value: summary.variant }, { label: "Model year", value: summary.modelYear }, { label: "Fuel", value: summary.fuelType }, { label: "Engine capacity", value: summary.engineCapacity }, { label: "Engine power", value: summary.enginePower }, { label: "Body type", value: summary.bodyType }, { label: "Color", value: summary.color }, { label: "Owners", value: summary.ownersCount }, { label: "Co-owners", value: summary.coOwnersCount }, { label: "Last ownership change", value: summary.lastOwnershipChange },
  ].filter((entry) => entry.value !== null && entry.value !== undefined && entry.value !== "");
}

function buildSourceStatusEntries(identity, report, summary) {
  return [
    { label: "Historia Pojazdu API", value: report.api_version || "—" },
    { label: "Advert id", value: identity.advertId || "—" },
    { label: "AutoDNA", value: providerAvailabilityLabel({ available: summary.autodnaAvailable, unavailable: summary.autodnaUnavailable, providerData: report.autodna_data }) },
    { label: "Carfax", value: providerAvailabilityLabel({ available: summary.carfaxAvailable, unavailable: summary.carfaxUnavailable, providerData: report.carfax_data }) },
  ];
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

function statusLabel(data, loading) {
  if (data?.report) return "Cached report ready";
  if (data?.status === "running") return "Searching";
  if (data?.status === "cancelling") return "Cancelling";
  if (data?.status === "cancelled") return "Cancelled";
  if (data?.status === "needs_input") return "Needs input";
  return loading ? "Fetching report" : "Waiting";
}
