import { useEffect, useRef, useCallback } from "react";
import { AUTOSAVE_DEBOUNCE } from "@/lib/constants";

export function useAutoSave<T>(key: string, data: T, enabled = true) {
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (!enabled) return;

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      localStorage.setItem(
        key,
        JSON.stringify({ data, savedAt: new Date().toISOString() }),
      );
    }, AUTOSAVE_DEBOUNCE);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [key, data, enabled]);

  const load = useCallback((): T | null => {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw).data as T;
    } catch {
      return null;
    }
  }, [key]);

  const clear = useCallback(() => {
    localStorage.removeItem(key);
  }, [key]);

  return { load, clear };
}
