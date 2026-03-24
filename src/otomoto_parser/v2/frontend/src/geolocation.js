export function getInitialGeolocationPlan({
  hasGeolocation,
  isSecureContext,
  hasPermissionsApi,
  permissionState,
}) {
  if (!hasGeolocation || !isSecureContext) {
    return { status: "unavailable", shouldRequestPosition: false };
  }
  if (!hasPermissionsApi) {
    return { status: "prompt", shouldRequestPosition: false };
  }
  if (permissionState === "granted") {
    return { status: "idle", shouldRequestPosition: true };
  }
  if (permissionState === "denied") {
    return { status: "denied", shouldRequestPosition: false };
  }
  return { status: "prompt", shouldRequestPosition: false };
}

export function getGeolocationErrorStatus({ errorCode, permissionState }) {
  if (permissionState === "denied" || errorCode === 1) {
    return "denied";
  }
  return "error";
}
