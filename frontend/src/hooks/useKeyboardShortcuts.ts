"use client";
import { useEffect } from "react";

interface ShortcutMap {
  [combo: string]: () => void;
}

export function useKeyboardShortcuts(shortcuts: ShortcutMap, enabled = true) {
  useEffect(() => {
    if (!enabled) return;

    function handler(e: KeyboardEvent) {
      // Skip when focus is on inputs
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const parts: string[] = [];
      if (e.metaKey || e.ctrlKey) parts.push("mod");
      if (e.shiftKey) parts.push("shift");
      if (e.altKey) parts.push("alt");

      const key = e.key.toLowerCase();
      if (!["meta", "control", "shift", "alt"].includes(key)) {
        parts.push(key === " " ? "space" : key);
      }

      const combo = parts.join("+");
      const fn = shortcuts[combo];
      if (fn) {
        e.preventDefault();
        fn();
      }
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [shortcuts, enabled]);
}
