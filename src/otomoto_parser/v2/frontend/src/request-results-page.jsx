import React from "react";
import { useParams } from "react-router-dom";

import { api } from "./api";
import { pageSizeOptions, systemCategoryOrder } from "./constants";
import { IconChevronLeft, IconChevronRight, IconEdit, IconPlus, IconTrash } from "./icons";
import { Breadcrumbs, IconButton, Shell, buildPageItems, scrollWindowToPosition } from "./layout";
import { formatDistanceChip, formatGeolocationStatus, getGeolocationButtonLabel } from "./location-utils";
import { ListingCard } from "./listing-card";
import { LocationModal } from "./location-modal";
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
  const categoryMap = dataState.results?.categories || {};
  const currentItems = dataState.results?.items || [];
  const geolocation = useResultsGeolocation(dataState.results, currentItems);

  usePagingEffects({ currentPage: dataState.currentPage, totalPages: dataState.results?.pagination?.totalPages || 1, safePage: dataState.results?.pagination?.page || 1, setCurrentPage: dataState.setCurrentPage, listTopRef, previousPageRef, paginationScrollRafRef });
  usePollingEffects({ requestId, reportState, redFlagState, setRedFlagState, loadRedFlagState, updateVehicleReportResultItem: dataState.updateVehicleReportResultItem });

  return (
    <Shell title="Categorized results" subtitle="Audit fresh inventory, move cars into your working buckets, and open deeper vehicle history context without leaving the board.">
      <Breadcrumbs items={[{ label: "Requests", to: "/" }, dataState.request ? { label: `Request ${dataState.request.id}`, to: `/requests/${dataState.request.id}` } : { label: "Request" }, { label: "Results" }]} />
      <section className="panel">
        {dataState.requestLoading ? <p className="muted">Loading request...</p> : null}
        {dataState.request && !dataState.request.resultsReady ? <><p className="progress-box">{dataState.request.progressMessage}</p><p className="muted">Results stay hidden until categorization finishes.</p></> : null}
        {dataState.resultsError && dataState.request?.resultsReady ? <p className="error-text">{dataState.resultsError}</p> : null}
        {dataState.results ? <ResultsSection dataState={dataState} geolocation={geolocation} categoryActions={categoryActions} listTopRef={listTopRef} setLocationPreview={setLocationPreview} reportState={reportState} /> : null}
      </section>
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
  const pageNumbers = buildPageItems(safePage, totalPages);
  return (
    <>
      <ResultsHeader dataState={dataState} geolocation={geolocation} />
      <ResultsTabs categoryEntries={categoryEntries} activeCategory={dataState.activeCategory} setActiveCategory={dataState.setActiveCategory} setCurrentPage={dataState.setCurrentPage} categoryMap={dataState.results?.categories || {}} categoryActions={categoryActions} />
      <div ref={listTopRef} className="results-list-top" />
      <div className="listing-grid">{currentItems.length === 0 ? <p className="muted">No listings in this category.</p> : currentItems.map((item) => <ListingCard key={item.id} item={item} assignableCategories={dataState.results?.assignableCategories || []} categoryBusy={Boolean(dataState.categoryBusyByListing[item.id])} onAssignCategories={categoryActions.assignSavedCategories} onCreateCategory={dataState.createCategory} onOpenLocation={setLocationPreview} onOpenReport={reportState.openVehicleReport} distanceLabel={formatDistanceChip(item.location, geolocation.geolocationState, geolocation.locationCache[item.location])} />)}</div>
      {currentItems.length > 0 ? <PaginationFooter results={dataState.results} safePage={safePage} pageSize={dataState.pageSize} totalPages={totalPages} pageNumbers={pageNumbers} setCurrentPage={dataState.setCurrentPage} /> : null}
    </>
  );
}

function ResultsHeader({ dataState, geolocation }) {
  const currentCategory = dataState.results.categories[dataState.activeCategory];
  return (
    <div className="results-head">
      <div className="results-title-block">
        <h2>{dataState.results.totalCount} listings</h2>
        <p className="muted">Generated {new Date(dataState.results.generatedAt).toLocaleString()}</p>
        <div className="results-highlight-strip">
          <span className="results-highlight-card"><span>Active lane</span><strong>{currentCategory?.label || "—"}</strong></span>
          <span className="results-highlight-card"><span>In lane</span><strong>{currentCategory?.count || 0}</strong></span>
          <span className="results-highlight-card"><span>Assignable</span><strong>{dataState.results.assignableCategories?.length || 0}</strong></span>
        </div>
      </div>
      <div className="results-controls">
        <button type="button" className="button-secondary" onClick={geolocation.requestCurrentPosition} disabled={!dataState.results || geolocation.geolocationState.status === "requesting" || geolocation.geolocationState.status === "unavailable"}>{getGeolocationButtonLabel(geolocation.geolocationState)}</button>
        <span className="muted results-location-status">{formatGeolocationStatus(geolocation.geolocationState)}</span>
        <label className="page-size-control"><span className="chip-label">Per page</span><select value={dataState.pageSize} onChange={(event) => { dataState.setCurrentPage(1); dataState.setPageSize(Number(event.target.value)); }}>{pageSizeOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
      </div>
    </div>
  );
}

function ResultsTabs({ categoryEntries, activeCategory, setActiveCategory, setCurrentPage, categoryMap, categoryActions }) {
  return (
    <div className="tab-row">
      {categoryEntries.map(([categoryKey, category]) => <button key={categoryKey} className={categoryKey === activeCategory ? "tab active" : "tab"} onClick={() => { setCurrentPage(1); setActiveCategory(categoryKey); }}><span className="tab-label">{category.label}</span><span className="tab-count">{category.count || 0}</span></button>)}
      <div className="tab-row-actions">
        <IconButton title="Add category" tone="secondary" onClick={() => void categoryActions.createCategoryTab()}><IconPlus /></IconButton>
        {categoryMap[activeCategory]?.editable ? <IconButton title="Rename category" tone="secondary" onClick={categoryActions.renameActiveCategory}><IconEdit /></IconButton> : null}
        {categoryMap[activeCategory]?.deletable ? <IconButton title="Delete category" tone="danger" onClick={categoryActions.deleteActiveCategory}><IconTrash /></IconButton> : null}
      </div>
    </div>
  );
}

function PaginationFooter({ results, safePage, pageSize, totalPages, pageNumbers, setCurrentPage }) {
  return (
    <div className="results-footer">
      <div className="pagination">
        <button type="button" className="pagination-button pagination-button-icon" disabled={safePage === 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))} aria-label="Previous page" title="Previous page"><IconChevronLeft /></button>
        {pageNumbers.map((page, index) => page === "ellipsis" ? <span key={`ellipsis-${index}`} className="pagination-ellipsis">…</span> : <button key={page} type="button" className={page === safePage ? "pagination-button active" : "pagination-button"} onClick={() => setCurrentPage(page)}>{page}</button>)}
        <button type="button" className="pagination-button pagination-button-icon" disabled={safePage === totalPages} onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))} aria-label="Next page" title="Next page"><IconChevronRight /></button>
      </div>
      <p className="muted">{`Showing ${Math.min(results.pagination.totalItems, (safePage - 1) * pageSize + 1)}-${Math.min(results.pagination.totalItems, safePage * pageSize)} of ${results.pagination.totalItems}`}</p>
    </div>
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
