import { createContext, useContext, useEffect, useMemo, type PropsWithChildren } from "react";
import { studioTheme, type ApplicationTheme } from "./theme";
interface Value { readonly theme: ApplicationTheme; }
const ThemeContext = createContext<Value | null>(null);
export function ThemeProvider({ children }: PropsWithChildren) { const value = useMemo(() => ({ theme: studioTheme }), []); useEffect(() => { document.documentElement.dataset.theme = value.theme.id; }, [value.theme.id]); return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>; }
export function useTheme() { const value = useContext(ThemeContext); if (!value) throw new Error("useTheme must be used within ThemeProvider."); return value; }
