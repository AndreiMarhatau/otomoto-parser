import React from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "./api";
import { inProgressStatuses } from "./constants";
import { compactSourceUrl, describeSourceUrl } from "./formatters";
import { IconDownload, IconExternal, IconTrash } from "./icons";
import { Breadcrumbs, Metric, Shell, StatusPill } from "./layout";
import { usePolling } from "./use-polling";

export function RequestDetailPage() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, reload } = usePolling(() => api(`/api/requests/${requestId}`), true, `/api/requests/${requestId}`);
  const item = data?.item;

  async function trigger(path) {
    await api(path, { method: "POST" });
    await reload();
  }

  async function removeRequest() {
    if (inProgressStatuses.has(item.status)) return window.alert("This request is still running and cannot be removed yet.");
    if (!window.confirm("Remove this request and its stored files?")) return;
    try {
      await api(`/api/requests/${requestId}`, { method: "DELETE" });
      navigate("/");
    } catch (removeError) {
      window.alert(removeError.message);
    }
  }

  if (loading && !item) return <Shell title="Request details" subtitle="Inspect parser progress and reopen outputs from a single request."><Typography color="text.secondary">Loading request...</Typography></Shell>;
  if (error && !item) return <Shell title="Request details" subtitle="Inspect parser progress and reopen outputs from a single request."><Alert severity="error">{error.message}</Alert></Shell>;
  const sourceMeta = describeSourceUrl(item.sourceUrl);
  return (
    <Shell title={`Request ${item.id}`} subtitle="Single request status with clearer sections for reruns, outputs, and cleanup." maxWidth="lg">
      <Breadcrumbs items={[{ label: "Requests", to: "/" }, { label: "Details" }]} />
      <Card variant="outlined">
        <CardContent>
          <Stack spacing={3}>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.55fr) minmax(260px, 0.9fr)" },
                gap: 2,
              }}
            >
              <Paper variant="outlined" sx={{ p: 2.25 }}>
                <Stack spacing={1.5}>
                  <Typography variant="overline" color="text.secondary">Source</Typography>
                  <StatusPill status={item.status} />
                  {sourceMeta.href ? (
                    <Button
                      component="a"
                      href={sourceMeta.href}
                      target="_blank"
                      rel="noreferrer"
                      endIcon={<IconExternal />}
                      variant="text"
                      sx={{ alignSelf: "flex-start", px: 0 }}
                    >
                      {compactSourceUrl(sourceMeta.displayValue, 72)}
                    </Button>
                  ) : (
                    <Typography>{compactSourceUrl(sourceMeta.displayValue, 72)}</Typography>
                  )}
                  <Typography variant="body2" color="text.secondary">{item.progressMessage}</Typography>
                </Stack>
              </Paper>
              <Paper variant="outlined" sx={{ p: 2.25 }}>
                <Stack spacing={1.5}>
                  <Typography variant="overline" color="text.secondary">Actions</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Resume, rerun, export, or remove this request from storage.
                  </Typography>
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<IconTrash />}
                    disabled={inProgressStatuses.has(item.status)}
                    onClick={removeRequest}
                    sx={{ alignSelf: "flex-start" }}
                  >
                    Delete request
                  </Button>
                </Stack>
              </Paper>
            </Box>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 1.5 }}>
              <Metric label="Pages completed" value={item.pagesCompleted} />
              <Metric label="Listings written" value={item.resultsWritten} />
              <Metric label="Results" value={item.resultsReady ? "Ready" : "Not ready"} />
              <Metric label="Excel export" value={item.excelReady ? "Ready" : "Pending"} />
            </Box>
            <Divider />
            <Paper variant="outlined" sx={{ p: 2.25 }}>
              <Stack spacing={1.25}>
                <Typography variant="subtitle2">Run controls</Typography>
                <Stack direction={{ xs: "column", md: "row" }} spacing={1.25} useFlexGap flexWrap="wrap">
                  <Button onClick={() => trigger(`/api/requests/${item.id}/resume`)} disabled={inProgressStatuses.has(item.status)} variant="contained">Resume and gather new</Button>
                  <Button onClick={() => trigger(`/api/requests/${item.id}/redo`)} disabled={inProgressStatuses.has(item.status)} variant="outlined">Redo from scratch</Button>
                  <Button component={Link} to={item.resultsReady ? `/requests/${item.id}/results` : "#"} disabled={!item.resultsReady} variant="outlined">Open results</Button>
                  <Button component="a" href={item.excelReady ? `/api/requests/${item.id}/excel` : undefined} disabled={!item.excelReady} variant="outlined" startIcon={<IconDownload />}>Download Excel</Button>
                </Stack>
              </Stack>
            </Paper>
            <Alert severity={item.error ? "error" : "info"} sx={{ alignItems: "center" }}>
              {item.error || item.progressMessage}
            </Alert>
          </Stack>
        </CardContent>
      </Card>
    </Shell>
  );
}
