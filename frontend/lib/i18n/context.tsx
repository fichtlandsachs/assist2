"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import de, { type TranslationKey } from "./de";
import en from "./en";

export type Locale = "de" | "en";

const STORAGE_KEY = "hk_locale";
const VALID_LOCALES: Locale[] = ["de", "en"];

function isValidLocale(v: unknown): v is Locale {
  return typeof v === "string" && (VALID_LOCALES as string[]).includes(v);
}

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return "de";
  const v = localStorage.getItem(STORAGE_KEY);
  return isValidLocale(v) ? v : "de";
}

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: TranslationKey, vars?: Record<string, string>) => string;
}

const I18nContext = createContext<I18nContextValue>({
  locale: "de",
  setLocale: () => {},
  t: (key) => de[key] ?? key,
});

// Allows the auth context to push the user's locale without prop-drilling
const externalSetLocale = { fn: null as ((l: Locale) => void) | null };
export function pushLocale(l: Locale) {
  externalSetLocale.fn?.(l);
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("de");

  // Hydrate from localStorage after mount
  useEffect(() => {
    const stored = readStoredLocale();
    setLocaleState(stored);
  }, []);

  const setLocale = useCallback((l: Locale) => {
    if (!isValidLocale(l)) return;
    setLocaleState(l);
    localStorage.setItem(STORAGE_KEY, l);
  }, []);

  // Register setter for external callers
  const setLocaleRef = useRef(setLocale);
  setLocaleRef.current = setLocale;
  useEffect(() => {
    externalSetLocale.fn = (l) => setLocaleRef.current(l);
    return () => { externalSetLocale.fn = null; };
  }, []);

  const dicts = { de, en } as const;

  const t = useCallback(
    (key: TranslationKey, vars?: Record<string, string>): string => {
      const dict = dicts[locale] as Record<string, string>;
      const fallback = dicts.de as Record<string, string>;
      let text: string = dict[key] ?? fallback[key] ?? key;
      if (vars) {
        Object.entries(vars).forEach(([k, v]) => {
          text = text.replaceAll(`{${k}}`, v);
        });
      }
      return text;
    },
    [locale] // eslint-disable-line react-hooks/exhaustive-deps
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useT() {
  return useContext(I18nContext);
}
