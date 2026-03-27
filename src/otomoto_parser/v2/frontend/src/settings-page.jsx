import React from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import { api } from "./api";
import { Breadcrumbs, Metric, Shell } from "./layout";
import { usePolling } from "./use-polling";

export function SettingsPage() {
  const { data, loading, error, reload } = usePolling(() => api("/api/settings"), false, "/api/settings");
  const settings = data?.item;
  const [openaiApiKey, setOpenaiApiKey] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState(null);

  async function persist(openaiApiKeyValue) {
    setSaving(true);
    setSaveError(null);
    try {
      await api("/api/settings", { method: "PUT", body: JSON.stringify({ openaiApiKey: openaiApiKeyValue }) });
      setOpenaiApiKey("");
      await reload();
    } catch (submitError) {
      setSaveError(submitError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Shell title="Settings" subtitle="Model configuration stays compact until you need it.">
      <Breadcrumbs items={[{ label: "Requests", to: "/" }, { label: "Settings" }]} />
      <Card variant="outlined">
        <CardContent>
          <Stack spacing={2.5}>
            <div>
              <Typography variant="overline" color="text.secondary">OpenAI</Typography>
              <Typography variant="h5">Red-flag analysis</Typography>
              <Typography variant="body2" color="text.secondary">Red-flag analysis uses GPT-5.4 with web search. Stored keys override `OPENAI_API_KEY` from the server environment.</Typography>
            </div>
            {loading ? <Typography color="text.secondary">Loading settings...</Typography> : null}
            {error ? <Alert severity="error">{error.message}</Alert> : null}
            {settings ? <SettingsStatus settings={settings} /> : null}
            <Stack component="form" spacing={2} onSubmit={(event) => { event.preventDefault(); void persist(openaiApiKey); }}>
              <TextField type="password" value={openaiApiKey} onChange={(event) => setOpenaiApiKey(event.target.value)} placeholder="sk-..." autoComplete="off" label="OpenAI API key" />
              <Stack direction="row" spacing={1}>
                <Button type="submit" disabled={saving} variant="contained">{saving ? "Saving..." : "Save key"}</Button>
                <Button type="button" variant="outlined" disabled={saving || !(settings?.openaiApiKeyStored || openaiApiKey)} onClick={() => void persist("")}>Clear stored key</Button>
              </Stack>
              {saveError ? <Alert severity="error">{saveError}</Alert> : null}
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Shell>
  );
}

function SettingsStatus({ settings }) {
  return (
    <Stack direction="row" spacing={1.5} useFlexGap flexWrap="wrap">
      <Metric label="Configured" value={settings.openaiApiKeyConfigured ? "Yes" : "No"} />
      <Metric label="Source" value={settings.openaiApiKeySource || "None"} />
      <Metric label="Active key" value={settings.openaiApiKeyMasked || "Not configured"} />
    </Stack>
  );
}
