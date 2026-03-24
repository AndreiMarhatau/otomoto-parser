import React from "react";

export function usePolling(loader, enabled, reloadKey) {
  const [state, setState] = React.useState({ loading: true, error: null, data: null });
  const loaderRef = React.useRef(loader);

  React.useEffect(() => {
    loaderRef.current = loader;
  }, [loader]);

  const load = React.useCallback(async () => {
    try {
      const data = await loaderRef.current();
      setState({ loading: false, error: null, data });
      return data;
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error }));
      throw error;
    }
  }, []);

  React.useEffect(() => {
    let active = true;
    async function run() {
      try {
        const data = await loaderRef.current();
        if (active) setState({ loading: false, error: null, data });
      } catch (error) {
        if (active) setState({ loading: false, error, data: null });
      }
    }
    run();
    if (!enabled) {
      return () => {
        active = false;
      };
    }
    const timer = window.setInterval(run, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [enabled, reloadKey]);

  return { ...state, reload: load };
}
