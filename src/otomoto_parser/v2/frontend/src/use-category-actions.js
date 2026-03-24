import React from "react";

import { api } from "./api";
import { systemCategoryOrder } from "./constants";

export function useCategoryActions({ requestId, results, activeCategory, setActiveCategory, setCurrentPage, bumpResultsReload, setResultsError, createCategory, setCategoryBusyByListing }) {
  const createCategoryTab = React.useCallback(async () => {
    const created = await createCategory();
    if (!created) return;
    setCurrentPage(1);
    setActiveCategory(created.key);
    bumpResultsReload();
  }, [bumpResultsReload, createCategory, setActiveCategory, setCurrentPage]);

  const renameActiveCategory = React.useCallback(async () => {
    const activeMeta = results?.categories?.[activeCategory];
    if (!activeMeta?.editable) return;
    const name = window.prompt("Category name", activeMeta.label);
    if (name === null) return;
    try {
      await api(`/api/requests/${requestId}/categories/${encodeURIComponent(activeCategory)}`, { method: "PATCH", body: JSON.stringify({ name }) });
      bumpResultsReload();
      setResultsError(null);
    } catch (error) {
      setResultsError(error.message);
    }
  }, [activeCategory, bumpResultsReload, requestId, results, setResultsError]);

  const deleteActiveCategory = React.useCallback(async () => {
    const activeMeta = results?.categories?.[activeCategory];
    if (!activeMeta?.deletable || !window.confirm(`Delete category "${activeMeta.label}"?`)) return;
    try {
      await api(`/api/requests/${requestId}/categories/${encodeURIComponent(activeCategory)}`, { method: "DELETE" });
      setActiveCategory(systemCategoryOrder[0]);
      setCurrentPage(1);
      bumpResultsReload();
      setResultsError(null);
    } catch (error) {
      setResultsError(error.message);
    }
  }, [activeCategory, bumpResultsReload, requestId, results, setActiveCategory, setCurrentPage, setResultsError]);

  const assignSavedCategories = React.useCallback(async (item, categoryKeys) => {
    setCategoryBusyByListing((current) => ({ ...current, [item.id]: true }));
    try {
      await api(`/api/requests/${requestId}/listings/${item.id}/categories`, { method: "PUT", body: JSON.stringify({ categoryIds: categoryKeys }) });
      setResultsError(null);
      bumpResultsReload();
    } catch (error) {
      setResultsError(error.message);
    } finally {
      setCategoryBusyByListing((current) => ({ ...current, [item.id]: false }));
    }
  }, [bumpResultsReload, requestId, setCategoryBusyByListing, setResultsError]);

  return { createCategoryTab, renameActiveCategory, deleteActiveCategory, assignSavedCategories };
}
