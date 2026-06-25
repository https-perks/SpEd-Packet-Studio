import { useCallback, useEffect, useRef, useState } from "react";
export type AutosaveStatus = "idle" | "pending" | "saving" | "saved" | "error";
interface Options<T> { readonly value: T; readonly save: (value: T, signal: AbortSignal) => Promise<void>; readonly enabled?: boolean; readonly delayMs?: number; }
export function useAutosave<T>({ value, save, enabled = true, delayMs = 800 }: Options<T>) {
  const [status, setStatus] = useState<AutosaveStatus>("idle"); const lastQueuedValue = useRef(value); const saveRef = useRef(save); saveRef.current = save;
  const saveNow = useCallback(async (next: T, signal: AbortSignal) => { setStatus("saving"); try { await saveRef.current(next, signal); if (!signal.aborted) setStatus("saved"); } catch (error) { if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return; setStatus("error"); } }, []);
  useEffect(() => { if (!enabled || Object.is(value, lastQueuedValue.current)) return;
    lastQueuedValue.current = value;
    const controller = new AbortController(); setStatus("pending"); const timeout = window.setTimeout(() => void saveNow(value, controller.signal), delayMs);
    return () => { window.clearTimeout(timeout); controller.abort(); };
  }, [delayMs, enabled, saveNow, value]);
  const saveImmediately = useCallback(async () => {
    lastQueuedValue.current = value;
    const controller = new AbortController();
    await saveNow(value, controller.signal);
  }, [saveNow, value]);
  return { status, saveImmediately } as const;
}
