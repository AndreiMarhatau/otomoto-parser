import React from "react";
import {
  Box,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Typography,
} from "@mui/material";

import { formatFieldLabel, formatValue } from "./formatters";

export function DataPairs({ entries }) {
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableBody>
          {entries.map((entry) => (
            <TableRow key={entry.label}>
              <TableCell sx={{ width: "36%", color: "text.secondary" }}>{entry.label}</TableCell>
              <TableCell>{formatValue(entry.value)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function DataTree({ label, value }) {
  if (value === null || value === undefined || value === "") {
    return <Leaf label={label} value="—" />;
  }
  if (Array.isArray(value)) {
    return (
      <Branch label={label}>
        {value.map((entry, index) => (
          <DataTree key={`${label}-${index}`} label={`${label} ${index + 1}`} value={entry} />
        ))}
      </Branch>
    );
  }
  if (typeof value === "object") {
    return (
      <Branch label={label}>
        {Object.entries(value).map(([key, entry]) => (
          <DataTree key={key} label={formatFieldLabel(key)} value={entry} />
        ))}
      </Branch>
    );
  }
  return <Leaf label={label} value={formatValue(value)} />;
}

function Branch({ label, children }) {
  return (
    <Box sx={{ pl: 1.5, borderLeft: 1, borderColor: "divider" }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>{label}</Typography>
      <Stack spacing={1.25}>{children}</Stack>
    </Box>
  );
}

function Leaf({ label, value }) {
  return (
    <Paper variant="outlined" sx={{ px: 1.5, py: 1 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="body2">{value}</Typography>
    </Paper>
  );
}
