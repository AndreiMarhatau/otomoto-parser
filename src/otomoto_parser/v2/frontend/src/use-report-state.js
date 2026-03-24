import React from "react";

import { api } from "./api";

export function useReportState({ requestId, loadRedFlagState, updateVehicleReportResultItem, redFlagRequestRef, setRedFlagState }) {
  const [vehicleReportState, setVehicleReportState] = React.useState(null);
  const vehicleReportRequestRef = React.useRef(0);

  const openVehicleReport = React.useCallback(async (item) => {
    const requestToken = vehicleReportRequestRef.current + 1;
    vehicleReportRequestRef.current = requestToken;
    const analysisToken = redFlagRequestRef.current + 1;
    redFlagRequestRef.current = analysisToken;
    setVehicleReportState({ item, loading: true, regenerating: false, submittingLookup: false, cancellingLookup: false, error: null, data: null });
    setRedFlagState({ item, loading: true, running: false, cancelling: false, error: null, data: null });
    try {
      const payload = await api(`/api/requests/${requestId}/listings/${item.id}/vehicle-report`);
      if (vehicleReportRequestRef.current !== requestToken) return;
      setVehicleReportState({ item, loading: false, regenerating: false, submittingLookup: false, cancellingLookup: false, error: null, data: payload.item });
      updateVehicleReportResultItem(item.id, payload.item);
      void loadRedFlagState(item, analysisToken);
    } catch (error) {
      if (vehicleReportRequestRef.current !== requestToken) return;
      setVehicleReportState({ item, loading: false, regenerating: false, submittingLookup: false, cancellingLookup: false, error: error.message, data: null });
      updateVehicleReportResultItem(item.id, null, error.message);
      void loadRedFlagState(item, analysisToken);
    }
  }, [loadRedFlagState, redFlagRequestRef, requestId, setRedFlagState, updateVehicleReportResultItem]);

  const reportAction = React.useCallback((name, pathFactory) => async (payload) => {
    if (!vehicleReportState?.item) return;
    const item = vehicleReportState.item;
    const requestToken = vehicleReportRequestRef.current + 1;
    vehicleReportRequestRef.current = requestToken;
    setVehicleReportState((current) => ({ ...current, [name]: true, error: null }));
    try {
      const response = await api(pathFactory(item.id), payload ? { method: "POST", body: JSON.stringify(payload) } : { method: "POST" });
      if (vehicleReportRequestRef.current !== requestToken) return;
      setVehicleReportState({ item, loading: false, regenerating: false, submittingLookup: false, cancellingLookup: false, error: null, data: response.item });
      updateVehicleReportResultItem(item.id, response.item);
    } catch (error) {
      if (vehicleReportRequestRef.current === requestToken) setVehicleReportState((current) => ({ ...current, [name]: false, error: error.message }));
    }
  }, [requestId, updateVehicleReportResultItem, vehicleReportState]);

  const regenerateVehicleReport = reportAction("regenerating", (itemId) => `/api/requests/${requestId}/listings/${itemId}/vehicle-report/regenerate`);
  const cancelVehicleReportLookup = reportAction("cancellingLookup", (itemId) => `/api/requests/${requestId}/listings/${itemId}/vehicle-report/lookup/cancel`);
  const submitVehicleReportLookup = reportAction("submittingLookup", (itemId) => `/api/requests/${requestId}/listings/${itemId}/vehicle-report/lookup`);

  return { vehicleReportState, setVehicleReportState, vehicleReportRequestRef, openVehicleReport, regenerateVehicleReport, submitVehicleReportLookup, cancelVehicleReportLookup };
}
