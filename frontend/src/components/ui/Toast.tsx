"use client";
import { useEffect } from "react";

export type ToastType = "success" | "error" | "info";

interface ToastProps {
  id: string;
  message: string;
  type: ToastType;
  onDismiss: (id: string) => void;
}

const styles: Record<ToastType, string> = {
  success: "bg-green-600 text-white",
  error: "bg-red-600 text-white",
  info: "bg-blue-600 text-white",
};

const icons: Record<ToastType, string> = {
  success: "\u2713",
  error: "\u2717",
  info: "\u2139",
};

export function Toast({ id, message, type, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(id), 4000);
    return () => clearTimeout(timer);
  }, [id, onDismiss]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${styles[type]} animate-in slide-in-from-right`}
    >
      <span aria-hidden="true">{icons[type]}</span>
      <span>{message}</span>
      <button
        onClick={() => onDismiss(id)}
        className="ml-2 opacity-70 hover:opacity-100"
        aria-label="Dismiss"
      >
        {"\u2715"}
      </button>
    </div>
  );
}
