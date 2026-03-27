import React from "react";
import {
  Alert,
  Card,
  CardContent,
  Pagination,
  Stack,
  Typography,
} from "@mui/material";
import { useParams } from "react-router-dom";

import { api } from "./api";
import { Breadcrumbs, Shell, buildPageItems, scrollWindowToPosition } from "./layout";
import { formatDistanceChip } from "./location-utils";
import { ListingCard } from "./listing-card";
import { LocationModal } from "./location-modal";
import { ResultsCategoryRail } from "./results-category-rail";
import { ResultsHeaderCard } from "./results-header-card";
import { useCategoryActions } from "./use-category-actions";
import { useRedFlagState } from "./use-red-flag-state";
import { useReportState } from "./use-report-state";
import { useResultsData } from "./use-results-data";
import { useResultsGeolocation } from "./use-results-geolocation";
import { VehicleReportModal } from "./vehicle-report-modal";

export function RequestResultsPage() {
  const { requestId } = useParams();
  const listTopRef = React.useRef(null);
  const previousPageRef = React.useRef(null);
  const paginationScrollRafRef = React.useRef(null);
  const dataState = useResultsData(requestId);
  const { redFlagState, setRedFlagState, redFlagRequestRef, loadRedFlagState, startRedFlagAnalysis, cancelRedFlagAnalysis } = useRedFlagState(requestId);
  const reportState = useReportState({ requestId, loadRedFlagState, updateVehicleReportResultItem: dataState.updateVehicleReportResultItem, redFlagRequestRef, setRedFlagState });
  const [locationPreview, setLocationPreview] = React.useState(null);
  const categoryActions = useCategoryActions({ requestId, results: dataState.results, activeCategory: dataState.activeCategory, setActiveCategory: dataState.setActiveCategory, setCurrentPage: dataState.setCurrentPage, bumpResultsReload: dataState.bumpResultsReload, setResultsError: dataState.setResultsError, createCategory: dataState.createCategory, setCategoryBusyByListing: dataState.setCategoryBusyByListing });
  const currentItems = dataState.results?.items || [];
  const geolocation = useResultsGeolocation(dataState.results, currentItems);

  usePagingEffects({ currentPage: dataState.currentPage, totalPages: dataState.results?.pagination?.totalPages || 1, safePage: dataState.results?.pagination?.page || 1, setCurrentPage: dataState.setCurrentPage, listTopRef, previousPageRef, paginationScrollRafRef });
  usePollingEffects({ requestId, reportState, redFlagState, setRedFlagState, loadRedFlagState, updateVehicleReportResultItem: dataState.updateVehicleReportResultItem });

  return (
    <Shell title="Results" subtitle="Listing review with clearer controls, stronger hierarchy, and a layout that stays readable on mobile." maxWidth="xl">
      <Breadcrumbs items={[{ label: "Requests", to: "/" }, dataState.request ? { label: `Request ${dataState.request.id}`, to: `/requests/${dataState.request.id}` } : { label: "Request" }, { label: "Results" }]} />
      <Stack spacing={2}>
        {dataState.requestLoading ? <Typography color="text.secondary">Loading request...</Typography> : null}
        {dataState.request && !dataState.request.resultsReady ? <Alert severity="info">{dataState.request.progressMessage}</Alert> : null}
        {dataState.resultsError && dataState.request?.resultsReady ? <Alert severity="error">{dataState.resultsError}</Alert> : null}
        {dataState.results ? <ResultsSection dataState={dataState} geolocation={geolocation} categoryActions={categoryActions} listTopRef={listTopRef} setLocationPreview={setLocationPreview} reportState={reportState} /> : null}
      </Stack>
      <LocationModal key={locationPreview ? `${locationPreview.title}-${locationPreview.location}` : "no-location-preview"} preview={locationPreview} onClose={() => setLocationPreview(null)} />
      <VehicleReportModal state={reportState.vehicleReportState} redFlagState={redFlagState} settings={dataState.settingsData?.item} onClose={() => closeModal(reportState, redFlagRequestRef, setRedFlagState)} onRegenerate={reportState.regenerateVehicleReport} onLookup={reportState.submitVehicleReportLookup} onCancelLookup={reportState.cancelVehicleReportLookup} onStartRedFlags={startRedFlagAnalysis} onCancelRedFlags={cancelRedFlagAnalysis} />
    </Shell>
  );
}

function ResultsSection({ dataState, geolocation, categoryActions, listTopRef, setLocationPreview, reportState }) {
  const categoryEntries = Object.entries(dataState.results?.categories || {});
  const currentItems = dataState.results?.items || [];
  const safePage = dataState.results?.pagination?.page || 1;
  const totalPages = dataState.results?.pagination?.totalPages || 1;
  buildPageItems(safePage, totalPages);
  return (
    <Stack spacing={2}>
      <Card variant="outlined">
        <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
          <ResultsHeaderCard dataState={dataState} geolocation={geolocation} />
        </CardContent>
      </Card>
      <ResultsCategoryRail categoryEntries={categoryEntries} activeCategory={dataState.activeCategory} setActiveCategory={dataState.setActiveCategory} setCurrentPage={dataState.setCurrentPage} categoryMap={dataState.results?.categories || {}} categoryActions={categoryActions} />
      <div ref={listTopRef} />
      <Stack spacing={1.5}>{currentItems.length === 0 ? <Typography color="text.secondary">No listings in this category.</Typography> : currentItems.map((item) => <ListingCard key={item.id} item={item} assignableCategories={dataState.results?.assignableCategories || []} categoryBusy={Boolean(dataState.categoryBusyByListing[item.id])} onAssignCategories={categoryActions.assignSavedCategories} onCreateCategory={dataState.createCategory} onOpenLocation={setLocationPreview} onOpenReport={reportState.openVehicleReport} distanceLabel={formatDistanceChip(item.location, geolocation.geolocationState, geolocation.locationCache[item.location])} />)}</Stack>
      {currentItems.length > 0 ? <PaginationFooter results={dataState.results} safePage={safePage} pageSize={dataState.pageSize} totalPages={totalPages} setCurrentPage={dataState.setCurrentPage} /> : null}
    </Stack>
  );
}

function PaginationFooter({ results, safePage, pageSize, totalPages, setCurrentPage }) {
  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} justifyContent="space-between" alignItems={{ sm: "center" }} sx={{ pt: 0.5 }}>
      <Pagination count={totalPages} page={safePage} onChange={(_, page) => setCurrentPage(page)} shape="rounded" />
      <Typography variant="body2" color="text.secondary">{`Showing ${Math.min(results.pagination.totalItems, (safePage - 1) * pageSize + 1)}-${Math.min(results.pagination.totalItems, safePage * pageSize)} of ${results.pagination.totalItems}`}</Typography>
    </Stack>
  );
}

function closeModal(reportState, redFlagRequestRef, setRedFlagState) {
  reportState.vehicleReportRequestRef.current += 1;
  redFlagRequestRef.current += 1;
  reportState.setVehicleReportState(null);
  setRedFlagState(null);
}

function usePagingEffects({ currentPage, totalPages, safePage, setCurrentPage, listTopRef, previousPageRef, paginationScrollRafRef }) {
  React.useEffect(() => { if (currentPage > totalPages) setCurrentPage(totalPages); }, [currentPage, setCurrentPage, totalPages]);
  React.useEffect(() => {
    if (previousPageRef.current === null) return void (previousPageRef.current = safePage);
    if (previousPageRef.current !== safePage) {
      if (paginationScrollRafRef.current !== null) window.cancelAnimationFrame(paginationScrollRafRef.current);
      paginationScrollRafRef.current = window.requestAnimationFrame(() => {
        paginationScrollRafRef.current = null;
        const top = listTopRef.current?.getBoundingClientRect?.().top;
        if (typeof top === "number") scrollWindowToPosition(Math.max(0, top + window.scrollY - 16));
      });
      previousPageRef.current = safePage;
    }
    return () => { if (paginationScrollRafRef.current !== null) { window.cancelAnimationFrame(paginationScrollRafRef.current); paginationScrollRafRef.current = null; } };
  }, [listTopRef, paginationScrollRafRef, previousPageRef, safePage]);
}

function usePollingEffects({ requestId, reportState, redFlagState, setRedFlagState, loadRedFlagState, updateVehicleReportResultItem }) {
  React.useEffect(() => {
    const state = reportState.vehicleReportState;
    if (!state?.item || state.loading || state.regenerating || state.submittingLookup || state.cancellingLookup || !["running", "cancelling"].includes(state.data?.status)) return undefined;
    let active = true;
    const timer = window.setInterval(async () => {
      try {
        const payload = await api(`/api/requests/${requestId}/listings/${state.item.id}/vehicle-report`);
        if (!active) return;
        reportState.setVehicleReportState((current) => (!current || current.item.id !== state.item.id ? current : { ...current, error: null, cancellingLookup: false, data: payload.item }));
        updateVehicleReportResultItem(state.item.id, payload.item);
      } catch (error) {
        if (active) reportState.setVehicleReportState((current) => current ? { ...current, error: error.message } : current);
      }
    }, 1500);
    return () => { active = false; window.clearInterval(timer); };
  }, [reportState, requestId, updateVehicleReportResultItem]);

  React.useEffect(() => {
    if (!redFlagState?.item || !["running", "cancelling"].includes(redFlagState.data?.status)) return undefined;
    let active = true;
    const timer = window.setInterval(async () => {
      try {
        const payload = await api(`/api/requests/${requestId}/listings/${redFlagState.item.id}/red-flags`);
        if (active) setRedFlagState((current) => (!current || current.item.id !== redFlagState.item.id ? current : { ...current, loading: false, running: false, cancelling: false, error: null, data: payload.item }));
      } catch (error) {
        if (active) setRedFlagState((current) => current ? { ...current, running: false, cancelling: false, error: error.message } : current);
      }
    }, 1500);
    return () => { active = false; window.clearInterval(timer); };
  }, [redFlagState, requestId, setRedFlagState]);

  React.useEffect(() => {
    const state = reportState.vehicleReportState;
    if (!state?.item || state.loading || state.regenerating || state.submittingLookup || state.cancellingLookup) return;
    if (redFlagState?.item?.id !== state.item.id) return;
    void loadRedFlagState(state.item);
  }, [loadRedFlagState, redFlagState?.item?.id, reportState.vehicleReportState, reportState.vehicleReportState?.data?.retrievedAt, reportState.vehicleReportState?.data?.reportSnapshotId, reportState.vehicleReportState?.data?.status, reportState.vehicleReportState?.data?.error]);
}
