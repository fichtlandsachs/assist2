"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";

export type ThemeId = "agile" | "paperwork" | "karl";

interface ThemeContextValue {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "agile",
  setTheme: () => {},
});

const STORAGE_KEY = "theme";
const VALID: ThemeId[] = ["agile", "paperwork", "karl"];

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>("karl");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    const initial: ThemeId = stored && VALID.includes(stored) ? stored : "karl";
    setThemeState(initial);
    document.documentElement.dataset.theme = initial;
  }, []);

  const setTheme = useCallback((t: ThemeId) => {
    setThemeState(t);
    document.documentElement.dataset.theme = t;
    localStorage.setItem(STORAGE_KEY, t);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
