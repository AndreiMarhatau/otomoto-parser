import React from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Button,
  Grid,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";

import { DataPairs, DataTree } from "./data-tree";
import { IconAlert } from "./icons";
import { normalizeLookupText } from "./formatters";

export function VehicleAnalysisSection({ analysisState, data, settings, busyFlags, onStartRedFlags, onCancelRedFlags }) {
  const redFlagData = analysisState?.data || null;
  const analysis = redFlagData?.analysis || null;
  const redFlagError = analysisState?.error || null;
  const ui = buildAnalysisUi({ analysisState, busyFlags, dataStatus: data?.status, redFlagData, settings });
  return (
    <Stack spacing={1.5}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1} justifyContent="space-between">
        <div>
          <Typography variant="h6">Find red flags</Typography>
          <Typography variant="body2" color="text.secondary">GPT-5.4 reviews the listing, the detail page, and the report when it is ready.</Typography>
        </div>
        <Stack direction="row" spacing={1}>
          <Button onClick={onStartRedFlags} disabled={ui.disabled} variant="contained">{ui.primaryLabel}</Button>
          {ui.showCancel ? <Button variant="outlined" onClick={onCancelRedFlags} disabled={ui.cancelDisabled}>{ui.cancelLabel}</Button> : null}
        </Stack>
      </Stack>
      {!data?.report ? <Alert icon={<IconAlert />} severity="warning">Analysis works better after the vehicle report is ready.</Alert> : null}
      {ui.showProgress ? <Alert severity="info">{redFlagData.progressMessage}</Alert> : null}
      {redFlagError ? <Alert severity="error">{redFlagError}</Alert> : null}
      {!redFlagError && redFlagData?.error ? <Alert severity="error">{redFlagData.error}</Alert> : null}
      {analysis ? <AnalysisResult analysis={analysis} /> : null}
    </Stack>
  );
}

export function VehicleLookupSection(props) {
  const { data, identity, lookupOptions, registrationNumber, dateFrom, dateTo, setRegistrationNumber, setDateFrom, setDateTo, busyFlags, onLookup, onCancelLookup } = props;
  const disabled = busyFlags.loading || busyFlags.regenerating || busyFlags.submittingLookup || busyFlags.cancellingLookup || data?.status === "running" || data?.status === "cancelling";
  return (
    <Stack spacing={1.5}>
      <Typography variant="h6">Lookup details</Typography>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, md: 3 }}>
          <TextField
            fullWidth
            size="small"
            label="VIN"
            value={identity.vin || lookupOptions.vin || "—"}
            slotProps={{ input: { readOnly: true } }}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <TextField
            fullWidth
            size="small"
            label="Registration number"
            value={registrationNumber}
            onChange={(event) => setRegistrationNumber(normalizeLookupText(event.target.value))}
            placeholder="Enter registration"
          />
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <TextField
            fullWidth
            size="small"
            label="First registration from"
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <TextField
            fullWidth
            size="small"
            label="Search until"
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Grid>
      </Grid>
      <Stack direction="row" spacing={1}>
        <Button variant="contained" disabled={disabled} onClick={() => onLookup({ registrationNumber: normalizeLookupText(registrationNumber), dateFrom, dateTo })}>
          {busyFlags.submittingLookup ? "Starting lookup..." : (data?.status === "running" || data?.status === "cancelling") ? "Lookup in progress" : "Search date range"}
        </Button>
        {data?.status === "running" || data?.status === "cancelling" ? (
          <Button variant="outlined" onClick={onCancelLookup} disabled={busyFlags.cancellingLookup || data?.status === "cancelling"}>
            {busyFlags.cancellingLookup || data?.status === "cancelling" ? "Cancelling..." : "Cancel lookup"}
          </Button>
        ) : null}
      </Stack>
    </Stack>
  );
}

export function VehicleReportDetails({ identity, report, summaryEntries, sourceStatusEntries }) {
  return (
    <Stack spacing={1.5}>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <Stack spacing={1}>
            <Typography variant="h6">Summary</Typography>
            <DataPairs entries={summaryEntries} />
          </Stack>
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <Stack spacing={1}>
            <Typography variant="h6">Source status</Typography>
            <DataPairs entries={sourceStatusEntries} />
          </Stack>
        </Grid>
      </Grid>
      <ReportAccordion title="Technical data" value={report.technical_data} defaultExpanded />
      <ReportAccordion title="AutoDNA" value={report.autodna_data} />
      <ReportAccordion title="Carfax" value={report.carfax_data} />
      <ReportAccordion title="Timeline" value={report.timeline_data} />
    </Stack>
  );
}

function AnalysisResult({ analysis }) {
  return (
    <Stack spacing={1.5}>
      <Alert severity="success">{analysis.summary}</Alert>
      <AnalysisGroup title="Serious red flags" empty="No serious red flags found." items={analysis.redFlags} tone="error" />
      <AnalysisGroup title="Warnings" empty="No warnings need attention." items={analysis.warnings} tone="warning" />
      <AnalysisGroup title="Green flags" empty="No positive signals identified." items={analysis.greenFlags} tone="success" />
      <Typography variant="body2" color="text.secondary">{analysis.webSearchUsed ? "Used web search for VIN-related checks." : "Did not need web search for this run."}</Typography>
    </Stack>
  );
}

function AnalysisGroup({ title, empty, items, tone }) {
  return items?.length ? (
    <Alert severity={tone}>
      <Typography variant="subtitle2">{title}</Typography>
      <ul>{items.map((flag) => <li key={flag}>{flag}</li>)}</ul>
    </Alert>
  ) : (
    <Typography variant="body2" color="text.secondary">{`${title}: ${empty}`}</Typography>
  );
}

function ReportAccordion({ title, value, defaultExpanded = false }) {
  return (
    <Accordion defaultExpanded={defaultExpanded}>
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography variant="subtitle2">{title}</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <DataTree label={title} value={value} />
      </AccordionDetails>
    </Accordion>
  );
}

function buildAnalysisUi({ analysisState, busyFlags, dataStatus, redFlagData, settings }) {
  const redFlagBusy = isAnalysisBusy(analysisState, redFlagData?.status);
  const apiKeyConfigured = settings?.openaiApiKeyConfigured || false;
  return {
    disabled: !apiKeyConfigured || redFlagBusy || isLookupBusy(busyFlags) || isRunningStatus(dataStatus),
    primaryLabel: redFlagBusy ? "Finding..." : redFlagData?.analysis ? "Run again" : "Find red flags",
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
