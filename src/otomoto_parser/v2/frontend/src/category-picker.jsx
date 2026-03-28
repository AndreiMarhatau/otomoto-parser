import React from "react";
import {
  Button,
  Checkbox,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
} from "@mui/material";

import { IconPlus, IconStar, IconTag } from "./icons";

export function CategoryPicker({ item, categories, busy, onCommit, onCreateCategory, onOpenChange }) {
  const [anchorEl, setAnchorEl] = React.useState(null);
  const [draftKeys, setDraftKeys] = React.useState(item.savedCategoryKeys || []);
  const [saving, setSaving] = React.useState(false);
  const open = Boolean(anchorEl);
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
    setAnchorEl(null);
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
    <>
      <Button
        variant="outlined"
        startIcon={<IconTag />}
        onClick={(event) => {
          event.stopPropagation();
          if (open) void closePicker();
          else setAnchorEl(event.currentTarget);
        }}
        disabled={busy || saving}
      >
        {selectedCount > 0 ? `Saved (${selectedCount})` : "Save"}
      </Button>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={() => void closePicker()}
        onClick={(event) => event.stopPropagation()}
        slotProps={{ paper: { sx: { minWidth: 240, borderRadius: 3 } } }}
      >
        {categories.map((category) => (
          <MenuItem key={category.key} dense onClick={() => toggleCategory(category.key)} disabled={busy || saving}>
            <Checkbox edge="start" checked={selectedKeys.has(category.key)} tabIndex={-1} disableRipple />
            <ListItemIcon sx={{ minWidth: 28 }}>{category.key === "Favorites" ? <IconStar fontSize="small" /> : <IconTag fontSize="small" />}</ListItemIcon>
            <ListItemText>{category.label}</ListItemText>
          </MenuItem>
        ))}
        <MenuItem dense onClick={() => void handleCreateCategory()} disabled={busy || saving}>
          <ListItemIcon sx={{ minWidth: 28 }}><IconPlus fontSize="small" /></ListItemIcon>
          <ListItemText>Add new</ListItemText>
        </MenuItem>
      </Menu>
    </>
  );
}
