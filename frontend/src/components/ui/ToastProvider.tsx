"use client";
import { createContext, useContext, useCallback, useState } from "react";
import { Toast, type ToastType } from "./Toast";

interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  addToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

let toastCounter = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((message: string, type: ToastType = "info") => {
    const id = `toast-${++toastCounter}`;
    setToasts((prev) => [...prev.slice(-4), { id, message, type }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
      >
        {toasts.map((t) => (
          <Toast key={t.id} id={t.id} message={t.message} type={t.type} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
