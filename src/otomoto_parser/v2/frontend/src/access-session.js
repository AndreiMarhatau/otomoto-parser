import { useEffect } from "react";
import { api } from "./api";

// Serialize renewal and credential mutations so a late renewal cannot restore
// an old cookie after logout/code rotation in this tab.
let pending = Promise.resolve();
export function accessRequest(body) {
  const work = pending.then(() => api("/api/access", { method: "POST", body: JSON.stringify(body) }));
  pending = work.catch(() => {});
  return work;
}

export function useAccessActivity() {
  useEffect(() => {
    let last = 0;
    const active = () => {
      if (document.visibilityState === "hidden" || Date.now() - last < 60_000) return;
      last = Date.now();
      void accessRequest({ action: "renew" }).catch(() => {
        // Normal app requests surface connection/authentication errors.
      });
    };
    active();
    for (const event of ["pointerdown", "keydown", "focus"]) window.addEventListener(event, active);
    return () => { for (const event of ["pointerdown", "keydown", "focus"]) window.removeEventListener(event, active); };
  }, []);
}
