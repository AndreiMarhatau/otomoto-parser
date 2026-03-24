import React from "react";

import { api } from "./api";

export function useRedFlagState(requestId) {
  const [redFlagState, setRedFlagState] = React.useState(null);
  const redFlagRequestRef = React.useRef(0);

  const loadRedFlagState = React.useCallback(async (item, requestToken = null) => {
    const payload = await api(`/api/requests/${requestId}/listings/${item.id}/red-flags`);
    if (requestToken !== null && redFlagRequestRef.current !== requestToken) return null;
    setRedFlagState((current) => (!current || current.item.id !== item.id ? current : { ...current, loading: false, running: false, cancelling: false, error: null, data: payload.item }));
    return payload.item;
  }, [requestId]);

  const action = React.useCallback((flag, pathFactory) => async () => {
    if (!redFlagState?.item) return;
    const item = redFlagState.item;
    const requestToken = redFlagRequestRef.current + 1;
    redFlagRequestRef.current = requestToken;
    setRedFlagState((current) => ({ ...current, [flag]: true, error: null }));
    try {
      const payload = await api(pathFactory(item.id), { method: "POST" });
      if (redFlagRequestRef.current === requestToken) setRedFlagState({ item, loading: false, running: false, cancelling: false, error: null, data: payload.item });
    } catch (error) {
      if (redFlagRequestRef.current === requestToken) setRedFlagState((current) => ({ ...current, [flag]: false, error: error.message }));
    }
  }, [redFlagState, requestId]);

  return { redFlagState, setRedFlagState, redFlagRequestRef, loadRedFlagState, startRedFlagAnalysis: action("running", (id) => `/api/requests/${requestId}/listings/${id}/red-flags`), cancelRedFlagAnalysis: action("cancelling", (id) => `/api/requests/${requestId}/listings/${id}/red-flags/cancel`) };
}
