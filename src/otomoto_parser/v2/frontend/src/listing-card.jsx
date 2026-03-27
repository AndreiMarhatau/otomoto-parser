import React from "react";
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CardMedia,
  Chip,
  Stack,
  Typography,
} from "@mui/material";

import { CategoryPicker } from "./category-picker";
import { IconCheckBadge, IconReport, IconXBadge } from "./icons";

export function ListingCard({ item, assignableCategories, categoryBusy, onAssignCategories, onCreateCategory, onOpenLocation, onOpenReport, distanceLabel }) {
  const [categoryPickerOpen, setCategoryPickerOpen] = React.useState(false);
  const createdAt = item.createdAt ? new Date(item.createdAt).toLocaleString() : "—";
  const reportStatus = item.vehicleReport?.status;
  const reportStateTitle = reportTitle(reportStatus, item.vehicleReport);
  const summarySpecs = listingSummarySpecs(item);
  const detailSpecs = listingDetailSpecs(item, createdAt);
  return (
    <Card sx={{ position: "relative", overflow: "visible" }}>
      <CardActionArea component="a" href={item.url} target="_blank" rel="noreferrer" sx={{ alignItems: "stretch" }}>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "176px 1fr" } }}>
          {item.imageUrl ? (
            <CardMedia component="img" image={item.imageUrl} alt={item.title} sx={{ height: { xs: 220, sm: "100%" } }} />
          ) : (
            <Box sx={{ minHeight: 180, bgcolor: "action.hover" }} />
          )}
          <CardContent sx={{ display: "grid", gap: 1.5 }}>
            <Stack direction="row" spacing={2} justifyContent="space-between" alignItems="flex-start">
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="h6" sx={{ pr: 1 }}>{item.title}</Typography>
                <Typography variant="body2" color="text.secondary">{item.shortDescription || "No short description."}</Typography>
              </Box>
              <Typography variant="h6" color="primary.main" sx={{ whiteSpace: "nowrap" }}>
                {item.price ? `${item.price.toLocaleString("pl-PL")} ${item.priceCurrency}` : "—"}
              </Typography>
            </Stack>
            <SpecRow specs={summarySpecs} />
            <ListingActions
              item={item}
              assignableCategories={assignableCategories}
              categoryBusy={categoryBusy}
              onAssignCategories={onAssignCategories}
              onCreateCategory={onCreateCategory}
              onOpenReport={onOpenReport}
              onOpenChange={setCategoryPickerOpen}
              reportStatus={reportStatus}
              reportStateTitle={reportStateTitle}
            />
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }}>
              {item.location ? (
                <Button
                  variant="text"
                  size="small"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onOpenLocation({ title: item.title, location: item.location });
                  }}
                >
                  {item.location}
                </Button>
              ) : (
                <Typography variant="body2" color="text.secondary">No location</Typography>
              )}
              <Typography variant="body2" color="text.secondary">{distanceLabel}</Typography>
            </Stack>
            <SpecRow specs={detailSpecs} />
          </CardContent>
        </Box>
      </CardActionArea>
      {categoryPickerOpen ? <Box sx={{ position: "absolute", inset: 0, pointerEvents: "none" }} /> : null}
    </Card>
  );
}

function ListingActions(props) {
  const { item, assignableCategories, categoryBusy, onAssignCategories, onCreateCategory, onOpenReport, onOpenChange, reportStatus, reportStateTitle } = props;
  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
      <CategoryPicker
        item={item}
        categories={assignableCategories}
        busy={categoryBusy}
        onCommit={onAssignCategories}
        onCreateCategory={onCreateCategory}
        onOpenChange={onOpenChange}
      />
      <Button
        variant="outlined"
        startIcon={<IconReport />}
        aria-label="Vehicle report"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenReport(item);
        }}
        endIcon={
          reportStatus === "success" ? <IconCheckBadge color="success" aria-hidden="true" /> :
          reportStatus === "failed" ? <IconXBadge color="error" aria-hidden="true" /> : null
        }
        title={reportStateTitle || "Open vehicle report"}
      >
        Vehicle report
      </Button>
    </Stack>
  );
}

function SpecRow({ specs }) {
  return (
    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
      {specs.map((spec) => <Chip key={spec.label} size="small" label={`${spec.label}: ${spec.value}`} />)}
    </Stack>
  );
}

function reportTitle(reportStatus, vehicleReport) {
  if (reportStatus === "success") return `Report fetched ${vehicleReport?.retrievedAt ? new Date(vehicleReport.retrievedAt).toLocaleString() : ""}`.trim();
  if (reportStatus === "failed") return vehicleReport?.lastAttemptAt ? `Previous fetch failed ${new Date(vehicleReport.lastAttemptAt).toLocaleString()}` : "Previous fetch failed";
  return null;
}

function listingSummarySpecs(item) {
  return [
    ...(item.category === "Price evaluation out of range" && item.dataVerified === true ? [{ label: "Status", value: "Verified data" }] : []),
    { label: "Price eval", value: item.priceEvaluation || "No price evaluation" },
    { label: "Year", value: item.year || "No year" },
    { label: "Mileage", value: item.mileage || "No mileage" },
  ];
}

function listingDetailSpecs(item, createdAt) {
  return [
    { label: "Engine", value: item.engineCapacity || "No engine capacity" },
    { label: "Power", value: item.enginePower || "No power" },
    { label: "Fuel", value: item.fuelType || "No fuel type" },
    { label: "Gearbox", value: item.transmission || "No transmission" },
    { label: "Created", value: createdAt },
  ];
}
