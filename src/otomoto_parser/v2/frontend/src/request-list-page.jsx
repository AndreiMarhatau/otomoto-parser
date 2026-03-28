import React from "react";
import {
  Alert,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";

import { api } from "./api";
import { inProgressStatuses } from "./constants";
import { compactSourceUrl, describeSourceUrl } from "./formatters";
import { IconClose, IconPlus, IconRefresh, IconTrash } from "./icons";
import { Shell, StatusPill } from "./layout";
import { usePolling } from "./use-polling";

export function RequestListPage() {
  const navigate = useNavigate();
  const openCreateButtonRef = React.useRef(null);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [url, setUrl] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState(null);
  const { data, loading, reload } = usePolling(() => api("/api/requests"), true, "/api/requests");
  const items = data?.items || [];

  async function submit(event) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const payload = await api("/api/requests", { method: "POST", body: JSON.stringify({ url }) });
      setCreateOpen(false);
      navigate(`/requests/${payload.item.id}`);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setCreating(false);
    }
  }

  async function removeRequest(requestId) {
    const request = items.find((item) => item.id === requestId);
    if (request && inProgressStatuses.has(request.status)) return window.alert("This request is still running and cannot be removed yet.");
    if (!window.confirm("Remove this request and its stored files?")) return;
    try {
      await api(`/api/requests/${requestId}`, { method: "DELETE" });
      await reload();
    } catch (removeError) {
      window.alert(removeError.message);
    }
  }

  return (
    <Shell
      title="Requests"
      subtitle="Review saved parser runs and reopen the ones that matter. Creation stays separate from history."
      actions={
        <>
          <Button ref={openCreateButtonRef} variant="contained" startIcon={<IconPlus />} onClick={() => { setUrl(""); setError(null); setCreateOpen(true); }}>
            New request
          </Button>
          <Button variant="outlined" startIcon={<IconRefresh />} onClick={() => reload()}>Refresh request list</Button>
        </>
      }
    >
      <Stack spacing={2}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1} justifyContent="space-between">
          <div>
            <Typography variant="overline" color="text.secondary">History</Typography>
            <Typography variant="h5">{items.length ? `${items.length} saved request${items.length === 1 ? "" : "s"}` : "History"}</Typography>
          </div>
          <Typography variant="body2" color="text.secondary">Runs stay here with their latest parser state and outputs.</Typography>
        </Stack>
        {loading ? <Typography color="text.secondary">Loading requests...</Typography> : null}
        {!loading && items.length === 0 ? <Alert severity="info">No requests yet. Use New request to start the first parser run.</Alert> : null}
        <Stack spacing={1.5}>{items.map((item) => <RequestRow key={item.id} item={item} navigate={navigate} onRemove={removeRequest} />)}</Stack>
      </Stack>
      <RequestCreateDialog
        open={createOpen}
        url={url}
        setUrl={setUrl}
        creating={creating}
        error={error}
        onSubmit={submit}
        onClose={() => { if (!creating) setCreateOpen(false); }}
      />
    </Shell>
  );
}

function RequestRow({ item, navigate, onRemove }) {
  const sourceMeta = describeSourceUrl(item.sourceUrl);
  return (
    <Card variant="outlined">
      <CardActionArea onClick={() => navigate(`/requests/${item.id}`)} sx={{ borderRadius: 3 }}>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between">
            <Stack spacing={1} sx={{ minWidth: 0 }}>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                <Typography variant="subtitle1">{`Request ${item.id}`}</Typography>
                <Typography variant="body2" color="text.secondary">{sourceMeta.label}</Typography>
              </Stack>
              <Typography variant="body2">{item.progressMessage}</Typography>
              <Typography variant="body2" color="text.secondary">{`${item.resultsWritten} listings • ${item.pagesCompleted} pages • ${new Date(item.createdAt).toLocaleString()}`}</Typography>
              {sourceMeta.href ? (
                <Typography component="a" href={sourceMeta.href} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} variant="body2" color="primary.main">
                  {compactSourceUrl(sourceMeta.displayValue, 56)}
                </Typography>
              ) : (
                <Typography variant="body2" color="text.secondary">{compactSourceUrl(sourceMeta.displayValue, 56)}</Typography>
              )}
            </Stack>
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <StatusPill status={item.status} />
              <IconButton
                aria-label="Delete request"
                color="error"
                disabled={inProgressStatuses.has(item.status)}
                onClick={(event) => {
                  event.stopPropagation();
                  onRemove(item.id);
                }}
              >
                <IconTrash />
              </IconButton>
            </Stack>
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function RequestCreateDialog({ open, url, setUrl, creating, error, onSubmit, onClose }) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pr: 6 }}>
        Create request
        <IconButton aria-label="Close dialog" onClick={onClose} sx={{ position: "absolute", right: 12, top: 12 }}>
          <IconClose />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Paste an OTOMOTO search URL. Parsing starts immediately and the run is added to history.
        </Typography>
        <form id="request-create-form" onSubmit={onSubmit}>
          <TextField
            multiline
            minRows={4}
            autoFocus
            fullWidth
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://www.otomoto.pl/osobowe/..."
            required
          />
        </form>
        {error ? <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert> : null}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button onClick={onClose} disabled={creating}>Cancel</Button>
        <Button type="submit" form="request-create-form" variant="contained" disabled={creating}>
          {creating ? "Creating..." : "Create request"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
