"use client";

import { createContext, useContext, type ReactNode } from "react";

interface ThemeContextValue {
  theme: "dark";
}

const ThemeContext = createContext<ThemeContextValue>({ theme: "dark" });

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <ThemeContext.Provider value={{ theme: "dark" }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
