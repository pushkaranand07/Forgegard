import { useSyncExternalStore } from "react";
import type { Analysis } from "./types";

// Analysis history lives in this browser only (the backend keeps no records).
const KEY = "fg-history-v1";
const MAX_ENTRIES = 60;

let cache: Analysis[] | null = null;
const listeners = new Set<() => void>();

function read(): Analysis[] {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(KEY);
    cache = raw ? (JSON.parse(raw) as Analysis[]) : [];
  } catch {
    cache = [];
  }
  return cache;
}

function write(next: Analysis[]) {
  cache = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Quota exceeded: drop thumbnails from older entries and retry once
    try {
      const slim = next.map((a, i) => (i < 10 ? a : { ...a, thumbnail: undefined }));
      localStorage.setItem(KEY, JSON.stringify(slim));
      cache = slim;
    } catch {
      // Storage unavailable (private mode) — keep the in-memory copy
    }
  }
  listeners.forEach((l) => l());
}

export const history = {
  all: read,
  get(id: string) {
    return read().find((a) => a.id === id);
  },
  add(...items: Analysis[]) {
    write([...items, ...read()].slice(0, MAX_ENTRIES));
  },
  remove(id: string) {
    write(read().filter((a) => a.id !== id));
  },
  clear() {
    write([]);
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY) {
        cache = null;
        listener();
      }
    };
    window.addEventListener("storage", onStorage);
    return () => {
      listeners.delete(listener);
      window.removeEventListener("storage", onStorage);
    };
  },
};

export function useHistory(): Analysis[] {
  return useSyncExternalStore(history.subscribe, history.all, () => []);
}
