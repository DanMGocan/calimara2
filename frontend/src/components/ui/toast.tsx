import { useState, useCallback, type ReactNode } from "react";
import { ToastContext, type ToastType } from "./toast-context";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

let nextId = 0;

const typeStyle: Record<ToastType, string> = {
  success: "text-[color:var(--color-ink)] border-[color:var(--color-ink)]",
  danger: "text-[color:var(--color-like)] border-[color:var(--color-like)]",
  info: "text-[color:var(--color-ink-soft)] border-[color:var(--color-hairline-strong)]",
};

const typeKicker: Record<ToastType, string> = {
  success: "ok",
  danger: "eroare",
  info: "info",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed top-5 right-5 z-[9999] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 rounded-[10px] border bg-[color:var(--color-paper)] px-4 py-3 text-sm font-medium transition-all animate-in slide-in-from-right-5 fade-in duration-200 ${typeStyle[toast.type]}`}
            style={{ minWidth: 260 }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: "var(--color-ink-faint)",
              }}
            >
              {typeKicker[toast.type]}
            </span>
            <span style={{ fontFamily: "var(--font-sans)", fontSize: 13 }}>{toast.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
