import React from "react";
import { DialogTitle, Stack, Typography } from "@mui/material";

import { IconClose, IconExternal, IconRefresh } from "./icons";
import { IconButton } from "./layout";

export function VehicleReportDialogHeader({ item, busyFlags, status, onClose, onRegenerate }) {
  return (
    <DialogTitle sx={{ p: { xs: 2, md: 3 }, pb: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between">
        <Stack spacing={0.5} sx={{ minWidth: 0 }}>
          <Typography component="div" variant="overline" color="text.secondary">Vehicle report</Typography>
          <Typography component="div" variant="h5" sx={{ lineHeight: 1.15 }}>{item.title}</Typography>
          <Typography component="div" variant="body2" color="text.secondary">{item.location || "Location unavailable"}</Typography>
        </Stack>
        <Stack direction="row" spacing={1} justifyContent={{ xs: "flex-start", md: "flex-end" }}>
          <IconButton title="Open listing" href={item.url} tone="secondary"><IconExternal /></IconButton>
          <IconButton title="Regenerate report" tone="secondary" onClick={onRegenerate} disabled={isModalActionDisabled(busyFlags, status)}><IconRefresh /></IconButton>
          <IconButton title="Close report" tone="secondary" onClick={onClose}><IconClose /></IconButton>
        </Stack>
      </Stack>
    </DialogTitle>
  );
}

function isModalActionDisabled(busyFlags, status) {
  return busyFlags.loading || busyFlags.regenerating || busyFlags.submittingLookup || busyFlags.cancellingLookup || ["running", "cancelling"].includes(status);
}
