"use client";
import { createContext, useContext, useState, useCallback, useEffect } from "react";

export type ThemeName = "dark" | "light";

interface ThemeContextValue {
  theme: ThemeName;
  setTheme: (name: ThemeName) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

export function ThemeProvider({ children, defaultTheme = "dark" }: { children: React.ReactNode; defaultTheme?: ThemeName }) {
  const [theme, setThemeState] = useState<ThemeName>(defaultTheme);

  const setTheme = useCallback((name: ThemeName) => {
    setThemeState(name);
    document.documentElement.setAttribute("data-theme", name);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState(prev => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      return next;
    });
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
