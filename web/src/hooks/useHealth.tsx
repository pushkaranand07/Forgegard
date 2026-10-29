import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { getHealth } from "../lib/api";
import { DEFAULT_LIMITS } from "../lib/analysis";
import type { HealthResponse } from "../lib/types";

type HealthState =
  | { state: "loading"; data: null; error: null }
  | { state: "ready"; data: HealthResponse; error: null }
  | { state: "offline"; data: null; error: string };

interface HealthContextValue {
  health: HealthState;
  limits: HealthResponse["limits"];
  checkedAt: Date | null;
  refresh: () => void;
}

const HealthContext = createContext<HealthContextValue | null>(null);

export function HealthProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<HealthState>({ state: "loading", data: null, error: null });
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const ctrl = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setHealth((h) => (h.state === "ready" ? h : { state: "loading", data: null, error: null }));
    getHealth(c.signal)
      .then((data) => {
        setHealth({ state: "ready", data, error: null });
        setCheckedAt(new Date());
      })
      .catch((e: Error) => {
        if (e.name === "AbortedError") return;
        setHealth({ state: "offline", data: null, error: e.message });
        setCheckedAt(new Date());
      });
  }, []);

  useEffect(() => {
    refresh();
    // Re-check periodically so the status pill recovers when the backend restarts
    const t = setInterval(refresh, 60_000);
    return () => {
      clearInterval(t);
      ctrl.current?.abort();
    };
  }, [refresh]);

  return (
    <HealthContext.Provider
      value={{ health, limits: health.data?.limits ?? DEFAULT_LIMITS, checkedAt, refresh }}
    >
      {children}
    </HealthContext.Provider>
  );
}

export function useHealth() {
  const ctx = useContext(HealthContext);
  if (!ctx) throw new Error("useHealth must be used inside <HealthProvider>");
  return ctx;
}
