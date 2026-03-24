import React from "react";

import { api } from "./api";
import { pageSizeOptions, systemCategoryOrder } from "./constants";
import { buildVehicleReportMeta } from "./formatters";
import { usePolling } from "./use-polling";

export function useResultsData(requestId) {
  const requestLoader = React.useCallback(() => api(`/api/requests/${requestId}`), [requestId]);
  const { data: requestData, loading: requestLoading } = usePolling(requestLoader, true, `/api/requests/${requestId}`);
  const { data: settingsData } = usePolling(() => api("/api/settings"), false, "/api/settings");
  const request = requestData?.item;
  const [results, setResults] = React.useState(null);
  const [resultsError, setResultsError] = React.useState(null);
  const [activeCategory, setActiveCategory] = React.useState(systemCategoryOrder[0]);
  const [pageSize, setPageSize] = React.useState(pageSizeOptions[0]);
  const [currentPage, setCurrentPage] = React.useState(1);
  const [reloadToken, setReloadToken] = React.useState(0);
  const [categoryBusyByListing, setCategoryBusyByListing] = React.useState({});

  React.useEffect(() => {
    setPageSize(pageSizeOptions[0]);
    setCurrentPage(1);
    setReloadToken(0);
  }, [requestId]);

  React.useEffect(() => {
    let active = true;
    async function loadResults() {
      try {
        const params = new URLSearchParams({ category: activeCategory, page: String(currentPage), page_size: String(pageSize) });
        const payload = await api(`/api/requests/${requestId}/results?${params.toString()}`);
        if (!active) return;
        setResults(payload);
        setResultsError(null);
        if (payload.currentCategory && payload.currentCategory !== activeCategory) setActiveCategory(payload.currentCategory);
      } catch (error) {
        if (active) {
          setResults(null);
          setResultsError(error.message);
        }
      }
    }
    loadResults();
    if (!request || !request.resultsReady) {
      const timer = window.setInterval(loadResults, 3000);
      return () => { active = false; window.clearInterval(timer); };
    }
    return () => { active = false; };
  }, [activeCategory, currentPage, pageSize, reloadToken, request, requestId]);

  const bumpResultsReload = React.useCallback(() => setReloadToken((value) => value + 1), []);
  const promptCategoryName = React.useCallback((initialValue = "") => window.prompt("Category name", initialValue), []);

  const submitCategoryCreation = React.useCallback(async (initialValue = "") => {
    const name = promptCategoryName(initialValue);
    if (name === null) return null;
    const payload = await api(`/api/requests/${requestId}/categories`, { method: "POST", body: JSON.stringify({ name }) });
    return payload.item;
  }, [promptCategoryName, requestId]);

  const createCategory = React.useCallback(async () => {
    try {
      const created = await submitCategoryCreation();
      if (!created) return null;
      setResults((current) => current ? { ...current, categories: { ...current.categories, [created.key]: { label: created.label, count: 0, kind: created.kind, editable: created.editable, deletable: created.deletable } }, assignableCategories: [...(current.assignableCategories || []), created] } : current);
      setResultsError(null);
      return created;
    } catch (error) {
      setResultsError(error.message);
      return null;
    }
  }, [submitCategoryCreation]);

  return { requestLoading, request, settingsData, results, resultsError, activeCategory, setActiveCategory, pageSize, setPageSize, currentPage, setCurrentPage, categoryBusyByListing, setCategoryBusyByListing, createCategory, bumpResultsReload, setResultsError, setResults, updateVehicleReportResultItem: buildResultMetaUpdater(setResults) };
}

function buildResultMetaUpdater(setResults) {
  return function updateVehicleReportResultItem(itemId, data, fallbackError = null) {
    setResults((current) => {
      if (!current) return current;
      return { ...current, items: (current.items || []).map((candidate) => candidate.id === itemId ? { ...candidate, vehicleReport: buildVehicleReportMeta(data, fallbackError) } : candidate) };
    });
  };
}
