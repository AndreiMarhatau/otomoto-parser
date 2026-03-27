import React from "react";

import { api } from "./api";
import { scrollWindowToPosition } from "./layout";

export function closeResultsModal(reportState, redFlagRequestRef, setRedFlagState) {
  reportState.vehicleReportRequestRef.current += 1;
  redFlagRequestRef.current += 1;
  reportState.setVehicleReportState(null);
  setRedFlagState(null);
}

export function useResultsPagingEffects({ currentPage, totalPages, safePage, setCurrentPage, listTopRef, previousPageRef, paginationScrollRafRef }) {
  React.useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [currentPage, setCurrentPage, totalPages]);

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
    return () => {
      if (paginationScrollRafRef.current !== null) {
        window.cancelAnimationFrame(paginationScrollRafRef.current);
        paginationScrollRafRef.current = null;
      }
    };
  }, [listTopRef, paginationScrollRafRef, previousPageRef, safePage]);
}

export function useResultsPollingEffects({ requestId, reportState, redFlagState, setRedFlagState, loadRedFlagState, updateVehicleReportResultItem }) {
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
    return () => {
      active = false;
      window.clearInterval(timer);
    };
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
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [redFlagState, requestId, setRedFlagState]);

  React.useEffect(() => {
    const state = reportState.vehicleReportState;
    if (!state?.item || state.loading || state.regenerating || state.submittingLookup || state.cancellingLookup) return;
    if (redFlagState?.item?.id !== state.item.id) return;
    void loadRedFlagState(state.item);
  }, [loadRedFlagState, redFlagState?.item?.id, reportState.vehicleReportState, reportState.vehicleReportState?.data?.retrievedAt, reportState.vehicleReportState?.data?.reportSnapshotId, reportState.vehicleReportState?.data?.status, reportState.vehicleReportState?.data?.error]);
}
