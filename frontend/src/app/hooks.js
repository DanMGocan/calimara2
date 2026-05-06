import { useEffect, useState } from "react";

export function useAsync(loader, deps) {
  const [state, setState] = useState({ data: null, error: "", loading: true });

  useEffect(() => {
    let cancelled = false;
    setState((current) => ({ ...current, error: "", loading: true }));
    loader()
      .then((data) => {
        if (!cancelled) setState({ data, error: "", loading: false });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({ data: null, error: error.message || "Cererea a eșuat.", loading: false });
        }
      });
    return () => {
      cancelled = true;
    };
  }, deps);

  return state;
}
