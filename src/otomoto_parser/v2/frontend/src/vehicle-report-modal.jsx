import React from "react";

import { normalizeLookupText } from "./formatters";
import { IconClose, IconExternal, IconRefresh } from "./icons";
import { IconButton } from "./layout";
import { VehicleAnalysisSection, VehicleLookupSection, VehicleReportDetails } from "./vehicle-report-sections";

export function VehicleReportModal({ state, redFlagState, settings, onClose, onRegenerate, onLookup, onCancelLookup, onStartRedFlags, onCancelRedFlags }) {
  const modalState = buildModalState(state);
  const progressMessage = buildProgressMessage(modalState.data, modalState.busyFlags);
  const [registrationNumber, setRegistrationNumber] = React.useState("");
  const [dateFrom, setDateFrom] = React.useState("");
  const [dateTo, setDateTo] = React.useState("");

  React.useEffect(() => {
    syncLookupInputs({
      stateId: state?.item?.id,
      activeLookup: modalState.activeLookup,
      lookupOptions: modalState.lookupOptions,
      identity: modalState.identity,
      setRegistrationNumber,
      setDateFrom,
      setDateTo,
    });
  }, [state?.item?.id, modalState.activeLookup.registrationNumber, modalState.identity.registrationNumber, modalState.lookupOptions.registrationNumber, modalState.lookupOptions.dateRange?.from, modalState.lookupOptions.dateRange?.to, modalState.activeLookup.dateRange?.from, modalState.activeLookup.dateRange?.to]);

  if (!state) return null;
  const { item, busyFlags, error, data, identity, summary, report, retrievedAt, lookupOptions, activeLookup } = modalState;
  const showLookupForm = shouldShowLookupForm(data);
  const summaryEntries = buildSummaryEntries(identity, summary);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel modal-panel-report" onClick={(event) => event.stopPropagation()}>
        <ModalHeader item={item} onClose={onClose} onRegenerate={onRegenerate} disabled={isModalActionDisabled(busyFlags, data?.status)} />
        <div className="modal-meta"><span className="chip chip-place"><span className="chip-label">Status</span><span>{statusLabel(data, busyFlags.loading)}</span></span><span className="chip chip-time"><span className="chip-label">Retrieved</span><span>{retrievedAt || "Not retrieved yet"}</span></span></div>
        <ModalMessages progressMessage={progressMessage} error={error} dataError={data?.error} />
        <VehicleAnalysisSection analysisState={redFlagState} data={data} settings={settings} busyFlags={busyFlags} onStartRedFlags={onStartRedFlags} onCancelRedFlags={onCancelRedFlags} />
        {showLookupForm ? <VehicleLookupSection data={data} identity={identity} lookupOptions={lookupOptions} activeLookup={activeLookup} registrationNumber={registrationNumber} dateFrom={dateFrom} dateTo={dateTo} setRegistrationNumber={setRegistrationNumber} setDateFrom={setDateFrom} setDateTo={setDateTo} busyFlags={busyFlags} onLookup={onLookup} onCancelLookup={onCancelLookup} /> : null}
        {data?.report ? <VehicleReportDetails identity={identity} report={report} summary={summary} summaryEntries={summaryEntries} /> : null}
      </div>
    </div>
  );
}

function ModalHeader({ item, onClose, onRegenerate, disabled }) {
  return (
    <div className="modal-head">
      <div><p className="eyebrow">Vehicle report</p><h2>{item.title}</h2><p className="muted">{item.location || "Location unavailable"}</p></div>
      <div className="modal-head-actions">
        <IconButton title="Open listing" href={item.url} tone="secondary"><IconExternal /></IconButton>
        <IconButton title="Regenerate report" tone="secondary" onClick={onRegenerate} disabled={disabled}><IconRefresh /></IconButton>
        <IconButton title="Close report" tone="secondary" onClick={onClose}><IconClose /></IconButton>
      </div>
    </div>
  );
}

function ModalMessages({ progressMessage, error, dataError }) {
  return (
    <>
      {progressMessage ? <p className="progress-box">{progressMessage}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!error && dataError ? <p className="error-text">{dataError}</p> : null}
    </>
  );
}

function setLookupState({ setRegistrationNumber, setDateFrom, setDateTo }) {
  setRegistrationNumber("");
  setDateFrom("");
  setDateTo("");
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

function syncLookupInputs({ stateId, activeLookup, lookupOptions, identity, setRegistrationNumber, setDateFrom, setDateTo }) {
  if (!stateId) {
    setLookupState({ setRegistrationNumber, setDateFrom, setDateTo });
    return;
  }
  setRegistrationNumber(normalizeLookupText(preferredLookupValue(activeLookup.registrationNumber, lookupOptions.registrationNumber, identity.registrationNumber)));
  setDateFrom(preferredLookupValue(lookupOptions.dateRange?.from, activeLookup.dateRange?.from));
  setDateTo(preferredLookupValue(lookupOptions.dateRange?.to, activeLookup.dateRange?.to));
}

function isModalActionDisabled(busyFlags, status) {
  return busyFlags.loading || busyFlags.regenerating || busyFlags.submittingLookup || busyFlags.cancellingLookup || ["running", "cancelling"].includes(status);
}

function buildProgressMessage(data, busyFlags) {
  if (busyFlags.loading) return "Fetching listing identity and vehicle history sources...";
  if (busyFlags.regenerating) return "Refreshing cached report...";
  if (busyFlags.cancellingLookup) return "Cancelling lookup...";
  if (!["running", "cancelling"].includes(data?.status)) return null;
  if (busyFlags.loading) return null;
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

function statusLabel(data, loading) {
  if (data?.report) return "Cached report ready";
  if (data?.status === "running") return "Searching";
  if (data?.status === "cancelling") return "Cancelling";
  if (data?.status === "cancelled") return "Cancelled";
  if (data?.status === "needs_input") return "Needs input";
  return loading ? "Fetching report" : "Waiting";
}
