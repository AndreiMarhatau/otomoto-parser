import React from "react";
import { Box, Card, CardContent, Stack, Tab, Tabs } from "@mui/material";

import { IconEdit, IconPlus, IconTrash } from "./icons";
import { IconButton } from "./layout";

export function ResultsCategoryRail({ categoryEntries, activeCategory, setActiveCategory, setCurrentPage, categoryMap, categoryActions }) {
  return (
    <Card variant="outlined">
      <CardContent sx={{ p: { xs: 1.5, md: 2 }, display: "flex", flexDirection: { xs: "column", lg: "row" }, gap: 1.5, alignItems: { lg: "center" }, justifyContent: "space-between" }}>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Tabs
            value={activeCategory}
            onChange={(_, categoryKey) => {
              setCurrentPage(1);
              setActiveCategory(categoryKey);
            }}
            aria-label="Result categories"
            variant="scrollable"
            scrollButtons={false}
            selectionFollowsFocus
            sx={{
              minHeight: 0,
              "& .MuiTabs-flexContainer": { gap: 1, pb: 0.25 },
              "& .MuiTabs-indicator": { display: "none" },
            }}
          >
            {categoryEntries.map(([categoryKey, category]) => (
              <Tab
                key={categoryKey}
                value={categoryKey}
                label={`${category.label} (${category.count || 0})`}
                disableRipple
                sx={{
                  minHeight: 0,
                  px: 1.5,
                  py: 1,
                  borderRadius: 999,
                  border: 1,
                  borderColor: "divider",
                  color: "text.secondary",
                  textTransform: "none",
                  fontWeight: 600,
                  alignItems: "center",
                  "&.Mui-selected": {
                    bgcolor: "primary.main",
                    borderColor: "primary.main",
                    color: "primary.contrastText",
                  },
                }}
              />
            ))}
          </Tabs>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center" justifyContent={{ xs: "space-between", sm: "flex-end" }}>
          <IconButton title="Add category" tone="secondary" onClick={() => void categoryActions.createCategoryTab()}><IconPlus /></IconButton>
          {categoryMap[activeCategory]?.editable ? <IconButton title="Rename category" tone="secondary" onClick={categoryActions.renameActiveCategory}><IconEdit /></IconButton> : null}
          {categoryMap[activeCategory]?.deletable ? <IconButton title="Delete category" tone="danger" onClick={categoryActions.deleteActiveCategory}><IconTrash /></IconButton> : null}
        </Stack>
      </CardContent>
    </Card>
  );
}
