import { useState, useCallback, type ReactNode } from "react";
import { ToastContext, type ToastType } from "./toast-context";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`
              rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg
              animate-in slide-in-from-right fade-in duration-200
              ${toast.type === "success" ? "bg-success" : ""}
              ${toast.type === "danger" ? "bg-danger" : ""}
              ${toast.type === "info" ? "bg-secondary" : ""}
            `}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
