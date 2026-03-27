import React from "react";
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from "@mui/material";

import { pageSizeOptions } from "./constants";
import { formatGeolocationStatus, getGeolocationButtonLabel } from "./location-utils";

export function ResultsHeaderCard({ dataState, geolocation }) {
  const activeCategoryMeta = dataState.results.categories?.[dataState.activeCategory];
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.2fr) minmax(300px, 0.8fr)" },
        gap: 2,
        alignItems: "start",
      }}
    >
      <Box>
        <Typography variant="overline" color="text.secondary">Review queue</Typography>
        <Typography variant="h4" sx={{ mt: 0.25 }}>{`${dataState.results.totalCount} listings`}</Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mt: 0.5 }}>
          {`${activeCategoryMeta?.label || "Category"}: ${dataState.results.pagination.totalItems} • Generated ${new Date(dataState.results.generatedAt).toLocaleString()}`}
        </Typography>
      </Box>
      <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} alignItems={{ sm: "center" }} justifyContent="space-between">
          <Stack spacing={0.5}>
            <Button
              variant="outlined"
              onClick={geolocation.requestCurrentPosition}
              disabled={!dataState.results || geolocation.geolocationState.status === "requesting" || geolocation.geolocationState.status === "unavailable"}
              sx={{ alignSelf: "flex-start" }}
            >
              {getGeolocationButtonLabel(geolocation.geolocationState)}
            </Button>
            <Typography variant="body2" color="text.secondary">{formatGeolocationStatus(geolocation.geolocationState)}</Typography>
          </Stack>
          <FormControl size="small" sx={{ minWidth: { xs: "100%", sm: 116 } }}>
            <InputLabel id="results-page-size-label">Per page</InputLabel>
            <Select
              labelId="results-page-size-label"
              label="Per page"
              value={String(dataState.pageSize)}
              onChange={(event) => {
                dataState.setCurrentPage(1);
                dataState.setPageSize(Number(event.target.value));
              }}
            >
              {pageSizeOptions.map((option) => <MenuItem key={option} value={String(option)}>{option}</MenuItem>)}
            </Select>
          </FormControl>
        </Stack>
      </Paper>
    </Box>
  );
}
