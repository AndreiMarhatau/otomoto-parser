import React from "react";

import { api } from "./api";
import { Breadcrumbs, Shell } from "./layout";
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
    <Shell title="Settings">
      <Breadcrumbs items={[{ label: "Requests", to: "/" }, { label: "Settings" }]} />
      <section className="panel settings-panel">
        <div><h2>OpenAI</h2><p className="muted">Red-flag analysis uses GPT-5.4 with web search. Stored keys override `OPENAI_API_KEY` from the server environment.</p></div>
        {loading ? <p className="muted">Loading settings...</p> : null}
        {error ? <p className="error-text">{error.message}</p> : null}
        {settings ? <SettingsStatus settings={settings} /> : null}
        <form className="request-form" onSubmit={(event) => { event.preventDefault(); void persist(openaiApiKey); }}>
          <label className="report-form-field"><span>OpenAI API key</span><input type="password" value={openaiApiKey} onChange={(event) => setOpenaiApiKey(event.target.value)} placeholder="sk-..." autoComplete="off" /></label>
          <div className="form-actions">
            <button type="submit" disabled={saving}>{saving ? "Saving..." : "Save key"}</button>
            <button type="button" className="button-secondary" disabled={saving || !(settings?.openaiApiKeyStored || openaiApiKey)} onClick={() => void persist("")}>Clear stored key</button>
          </div>
          {saveError ? <p className="error-text">{saveError}</p> : null}
        </form>
      </section>
    </Shell>
  );
}

function SettingsStatus({ settings }) {
  return (
    <div className="settings-status-grid">
      <div className="metric"><span>Configured</span><strong>{settings.openaiApiKeyConfigured ? "Yes" : "No"}</strong></div>
      <div className="metric"><span>Source</span><strong>{settings.openaiApiKeySource || "None"}</strong></div>
      <div className="metric"><span>Active key</span><strong>{settings.openaiApiKeyMasked || "Not configured"}</strong></div>
    </div>
  );
}
