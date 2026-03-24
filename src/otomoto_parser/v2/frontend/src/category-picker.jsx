import React from "react";

import { IconPlus, IconStar, IconTag } from "./icons";

export function CategoryPicker({ item, categories, busy, onCommit, onCreateCategory, onOpenChange }) {
  const [open, setOpen] = React.useState(false);
  const [draftKeys, setDraftKeys] = React.useState(item.savedCategoryKeys || []);
  const [saving, setSaving] = React.useState(false);
  const containerRef = React.useRef(null);
  const selectedKeys = new Set(draftKeys);
  const selectedCount = categories.filter((category) => selectedKeys.has(category.key)).length;

  React.useEffect(() => {
    onOpenChange?.(open);
  }, [onOpenChange, open]);

  React.useEffect(() => {
    if (!open) setDraftKeys(item.savedCategoryKeys || []);
  }, [item.savedCategoryKeys, open]);

  function orderedKeys(keys) {
    const selected = new Set(keys);
    return categories.map((category) => category.key).filter((key) => selected.has(key));
  }

  async function closePicker() {
    setOpen(false);
    const nextKeys = orderedKeys(draftKeys);
    const currentKeys = orderedKeys(item.savedCategoryKeys || []);
    if (JSON.stringify(nextKeys) === JSON.stringify(currentKeys)) return;
    setSaving(true);
    try {
      await onCommit(item, nextKeys);
    } finally {
      setSaving(false);
    }
  }

  React.useEffect(() => {
    if (!open) return undefined;
    function handlePointerDown(event) {
      if (!containerRef.current?.contains(event.target)) void closePicker();
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [draftKeys, item, open]);

  function toggleCategory(categoryKey) {
    const next = new Set(draftKeys);
    next.has(categoryKey) ? next.delete(categoryKey) : next.add(categoryKey);
    setDraftKeys(orderedKeys([...next]));
  }

  async function handleCreateCategory() {
    const created = await onCreateCategory();
    if (created) setDraftKeys((current) => [...new Set([...current, created.key])]);
  }

  return (
    <div className={open ? "category-picker open" : "category-picker"} ref={containerRef} onClick={(event) => event.stopPropagation()}>
      <button type="button" className="listing-category-button chip-interactive" onClick={() => (open ? void closePicker() : setOpen(true))} disabled={busy || saving} title="Manage saved categories">
        <IconTag /><span>Save</span>{selectedCount > 0 ? <span className="listing-category-count">{selectedCount}</span> : null}
      </button>
      {open ? (
        <div className="category-picker-menu">
          <div className="category-picker-list">
            {categories.map((category) => (
              <label key={category.key} className="category-picker-option">
                <input type="checkbox" checked={selectedKeys.has(category.key)} disabled={busy || saving} onChange={() => toggleCategory(category.key)} />
                <span className="category-picker-option-label">{category.key === "Favorites" ? <IconStar /> : <IconTag />}<span>{category.label}</span></span>
              </label>
            ))}
          </div>
          <button type="button" className="category-picker-add" disabled={busy || saving} onClick={() => void handleCreateCategory()}>
            <IconPlus /><span>Add new</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
