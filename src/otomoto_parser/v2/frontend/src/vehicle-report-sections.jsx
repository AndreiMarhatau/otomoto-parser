import React from "react";

import { DataPairs, DataTree } from "./data-tree";
import { IconAlert } from "./icons";
import { normalizeLookupText } from "./formatters";

export function VehicleAnalysisSection({ analysisState, data, settings, busyFlags, onStartRedFlags, onCancelRedFlags }) {
  const redFlagData = analysisState?.data || null;
  const analysis = redFlagData?.analysis || null;
  const redFlagError = analysisState?.error || null;
  const ui = buildAnalysisUi({ analysisState, busyFlags, dataStatus: data?.status, redFlagData, settings });
  return (
    <section className="report-section">
      <div className="analysis-section-head">
        <div><h3>Find red flags</h3><p className="muted">GPT-5.4 reviews the listing, the detail page, and the report when it is ready.</p></div>
        <div className="analysis-actions">
          <span title={ui.buttonTitle}>
            <button type="button" onClick={onStartRedFlags} disabled={ui.disabled}>{ui.primaryLabel}</button>
          </span>
          {ui.showCancel ? <button type="button" className="button-secondary" onClick={onCancelRedFlags} disabled={ui.cancelDisabled}>{ui.cancelLabel}</button> : null}
        </div>
      </div>
      {!data?.report ? <div className="warning-box"><IconAlert /><span>Analysis works better after the vehicle report is ready.</span></div> : null}
      {ui.showProgress ? <p className="progress-box">{redFlagData.progressMessage}</p> : null}
      {redFlagError ? <p className="error-text">{redFlagError}</p> : null}
      {!redFlagError && redFlagData?.error ? <p className="error-text">{redFlagData.error}</p> : null}
      {analysis ? <AnalysisResult analysis={analysis} /> : null}
    </section>
  );
}

export function VehicleLookupSection({ data, identity, lookupOptions, activeLookup, registrationNumber, dateFrom, dateTo, setRegistrationNumber, setDateFrom, setDateTo, busyFlags, onLookup, onCancelLookup }) {
  return (
    <section className="report-section">
      <h3>Lookup details</h3>
      <div className="report-pairs">
        <div className="report-pair"><span>VIN</span><strong>{identity.vin || lookupOptions.vin || "—"}</strong></div>
        <label className="report-form-field"><span>Registration</span><input type="text" value={registrationNumber} onChange={(event) => setRegistrationNumber(normalizeLookupText(event.target.value))} placeholder="Enter registration" /></label>
        <label className="report-form-field"><span>Date from</span><input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
        <label className="report-form-field"><span>Date to</span><input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
      </div>
      <div className="report-form-actions">
        <button type="button" onClick={() => onLookup({ registrationNumber: normalizeLookupText(registrationNumber), dateFrom, dateTo })} disabled={busyFlags.loading || busyFlags.regenerating || busyFlags.submittingLookup || busyFlags.cancellingLookup || data?.status === "running" || data?.status === "cancelling"}>
          {busyFlags.submittingLookup ? "Starting lookup..." : (data?.status === "running" || data?.status === "cancelling") ? "Lookup in progress" : "Search date range"}
        </button>
        {data?.status === "running" || data?.status === "cancelling" ? <button type="button" className="button-secondary" onClick={onCancelLookup} disabled={busyFlags.loading || busyFlags.regenerating || busyFlags.submittingLookup || busyFlags.cancellingLookup || data?.status === "cancelling"}>{busyFlags.cancellingLookup || data?.status === "cancelling" ? "Cancelling..." : "Cancel lookup"}</button> : null}
      </div>
    </section>
  );
}

export function VehicleReportDetails({ identity, report, summary, summaryEntries }) {
  return (
    <details className="report-details">
      <summary>View report</summary>
      <div className="report-layout">
        <section className="report-section"><h3>Summary</h3><DataPairs entries={summaryEntries} /></section>
        <section className="report-section"><h3>Source status</h3><DataPairs entries={[{ label: "Historia Pojazdu API", value: report.api_version || "—" }, { label: "AutoDNA payload", value: summary.autodnaAvailable ? "Available" : summary.autodnaUnavailable ? "Unavailable" : "Empty" }, { label: "Carfax payload", value: summary.carfaxAvailable ? "Available" : summary.carfaxUnavailable ? "Unavailable" : "Empty" }, { label: "Advert id", value: identity.advertId }]} /></section>
        <details className="report-details"><summary>Technical data</summary><DataTree label="Technical data" value={report.technical_data} /></details>
        <details className="report-details"><summary>AutoDNA</summary><DataTree label="AutoDNA" value={report.autodna_data} /></details>
        <details className="report-details"><summary>Carfax</summary><DataTree label="Carfax" value={report.carfax_data} /></details>
        <details className="report-details"><summary>Timeline</summary><DataTree label="Timeline" value={report.timeline_data} /></details>
      </div>
    </details>
  );
}

function AnalysisResult({ analysis }) {
  return (
    <div className="analysis-result">
      <p><strong>{analysis.summary}</strong></p>
      <AnalysisGroup title="Serious red flags" empty="No serious red flags found." items={analysis.redFlags} tone="critical" />
      <AnalysisGroup title="Warnings" empty="No warnings need attention." items={analysis.warnings} tone="warning" />
      <AnalysisGroup title="Green flags" empty="No positive signals identified." items={analysis.greenFlags} tone="positive" />
      <p className="muted">{analysis.webSearchUsed ? "Used web search for VIN-related checks." : "Did not need web search for this run."}</p>
    </div>
  );
}

function AnalysisGroup({ title, empty, items, tone }) {
  return (
    <div className="analysis-group">
      <h4>{title}</h4>
      {items?.length ? <ul className={`analysis-list analysis-list-${tone}`}>{items.map((flag) => <li key={flag}>{flag}</li>)}</ul> : <p className="muted">{empty}</p>}
    </div>
  );
}

function buildAnalysisUi({ analysisState, busyFlags, dataStatus, redFlagData, settings }) {
  const redFlagBusy = isAnalysisBusy(analysisState, redFlagData?.status);
  const apiKeyConfigured = settings?.openaiApiKeyConfigured || false;
  const disabled = !apiKeyConfigured || redFlagBusy || isLookupBusy(busyFlags) || isRunningStatus(dataStatus);
  return {
    buttonTitle: apiKeyConfigured
      ? "Find serious red flags with GPT-5.4"
      : "Set an OpenAI API key in Settings to enable red-flag analysis",
    primaryLabel: redFlagBusy ? "Finding..." : redFlagData?.analysis ? "Run again" : "Find red flags",
    disabled,
    showCancel: isRunningStatus(redFlagData?.status),
    cancelDisabled: analysisState?.cancelling || redFlagData?.status === "cancelling",
    cancelLabel: analysisState?.cancelling || redFlagData?.status === "cancelling" ? "Cancelling..." : "Cancel analysis",
    showProgress: redFlagBusy && Boolean(redFlagData?.progressMessage),
  };
}

function isAnalysisBusy(analysisState, status) {
  return analysisState?.loading || analysisState?.running || analysisState?.cancelling || isRunningStatus(status) || false;
}

function isLookupBusy(busyFlags) {
  return busyFlags.loading || busyFlags.regenerating || busyFlags.submittingLookup || busyFlags.cancellingLookup;
}

function isRunningStatus(status) {
  return status === "running" || status === "cancelling";
}
