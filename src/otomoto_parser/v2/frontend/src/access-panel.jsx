import React from "react";
import { Alert, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { api } from "./api";
import { Shell } from "./layout";

export function AccessPanel({ loginPage = false }) {
  const [status, setStatus] = React.useState(null);
  const [code, setCode] = React.useState("");
  const [newCode, setNewCode] = React.useState("");
  const [repeat, setRepeat] = React.useState("");
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const refresh = React.useCallback(async () => {
    try { setStatus(await api("/api/access")); }
    catch (e) { setError(e.message); }
  }, []);
  React.useEffect(() => { void refresh(); }, [refresh]);
  const locked = status?.enabled && !status?.authenticated;
  async function submit(action) {
    setError(""); setNotice("");
    if (action === "save" && newCode !== repeat) { setError("New codes do not match."); return; }
    setBusy(true);
    try {
      await api("/api/access", { method: "POST", body: JSON.stringify({ action: action === "disable" ? "save" : action, code, newCode: action === "disable" ? "" : newCode }) });
      setCode(""); setNewCode(""); setRepeat("");
      if (action === "login") window.location.assign("/");
      else if (action === "logout") window.location.assign("/access");
      else { await refresh(); setNotice(action === "disable" ? "Protection disabled." : "Code saved. Other sessions are signed out."); }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  const field = (label, value, setter, autoComplete, minimum) => <TextField label={label} type="password" value={value} onChange={e => setter(e.target.value)} autoComplete={autoComplete} required slotProps={{ htmlInput: { minLength: minimum, maxLength: 128 } }} />;
  const content = <Card variant="outlined"><CardContent><Stack spacing={2}>
    <Typography variant="h5">{locked ? "Sign in" : "Access code"}</Typography>
    {!status ? <Button onClick={refresh}>Retry loading access settings</Button> : <>
      <Typography color="text.secondary">{locked ? "Enter your access code." : status.enabled ? "Protection enabled. Enter the current code to change it." : "Protection disabled. Set a code on your trusted network before exposing this app."}</Typography>
      <Stack component="form" spacing={2} onSubmit={e => { e.preventDefault(); void submit(locked ? "login" : "save"); }}>
        {(locked || status.enabled) && field(locked ? "Access code" : "Current code", code, setCode, "current-password")}
        {!locked && <>
          {field("New code (8–128 characters)", newCode, setNewCode, "new-password", 8)}
          {field("Repeat new code", repeat, setRepeat, "new-password", 8)}
        </>}
        <Button type="submit" disabled={busy} variant="contained">{busy ? "Please wait..." : locked ? "Sign in" : "Save code"}</Button>
        {!locked && status.enabled && <>
          <Button type="button" disabled={busy || !code} onClick={() => { if (window.confirm("Disable protection? Anyone with the address can use this app.")) void submit("disable"); }}>Disable protection</Button>
          <Button type="button" disabled={busy} onClick={() => void submit("logout")}>Sign out</Button>
        </>}
      </Stack>
      <Typography variant="body2" color="text.secondary">This browser remembers your session. Regular use keeps it signed in; One year of inactivity requires the code again.</Typography>
    </>}
    {error && <Alert severity="error">{error}</Alert>}
    {notice && <Alert severity="success">{notice}</Alert>}
  </Stack></CardContent></Card>;
  return loginPage ? <Shell title="Otomoto Parser" subtitle="Access"><>{content}{!locked && status && <Button component="a" href="/">Back to application</Button>}</></Shell> : content;
}
