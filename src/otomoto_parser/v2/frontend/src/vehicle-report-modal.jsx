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

import { VehicleReportDialogHeader } from "./vehicle-report-dialog-header";
import {
  EMPTY_LOOKUP_DEFAULTS,
  areLookupDefaultsEqual,
  buildLookupDefaults,
  buildModalState,
  buildProgressMessage,
  buildSourceStatusEntries,
  buildSummaryEntries,
  emptyLookupFormState,
  shouldShowLookupForm,
  statusLabel,
  syncLookupFormState,
  updateLookupFormState,
} from "./vehicle-report-modal-state";
import { VehicleAnalysisSection, VehicleLookupSection, VehicleReportDetails } from "./vehicle-report-sections";

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
