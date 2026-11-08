import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Analysis } from "./types";

// history.ts keeps a module-level cache, so each test loads a fresh copy.
async function load() {
  vi.resetModules();
  return (await import("./history")).history;
}

class MemoryStorage {
  data = new Map<string, string>();
  failWrites = 0; // number of setItem calls that throw before succeeding
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    if (this.failWrites > 0) {
      this.failWrites--;
      throw new Error("QuotaExceededError");
    }
    this.data.set(k, v);
  }
}

let storage: MemoryStorage;
const events = new EventTarget();

beforeEach(() => {
  storage = new MemoryStorage();
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("window", {
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
  });
});
afterEach(() => vi.unstubAllGlobals());

const entry = (id: string, thumbnail?: string) => ({ id, thumbnail }) as Analysis;

describe("history (browser-local)", () => {
  it("adds newest first, gets, removes and clears", async () => {
    const h = await load();
    h.add(entry("a"));
    h.add(entry("b"));
    expect(h.all().map((x) => x.id)).toEqual(["b", "a"]);
    expect(h.get("a")?.id).toBe("a");
    h.remove("a");
    expect(h.get("a")).toBeUndefined();
    h.clear();
    expect(h.all()).toEqual([]);
  });

  it("keeps at most 60 entries", async () => {
    const h = await load();
    h.add(...Array.from({ length: 70 }, (_, i) => entry(String(i))));
    expect(h.all()).toHaveLength(60);
  });

  it("persists across reloads and survives corrupt storage", async () => {
    (await load()).add(entry("kept"));
    expect((await load()).get("kept")).toBeDefined();
    storage.data.set("fg-history-v1", "{not json");
    expect((await load()).all()).toEqual([]);
  });

  it("drops old thumbnails when the quota is exceeded", async () => {
    const h = await load();
    storage.failWrites = 1;
    h.add(...Array.from({ length: 12 }, (_, i) => entry(String(i), "data:x")));
    const saved = JSON.parse(storage.data.get("fg-history-v1")!) as Analysis[];
    expect(saved[0].thumbnail).toBe("data:x");
    expect(saved[11].thumbnail).toBeUndefined();
  });

  it("keeps working in memory when storage is unavailable", async () => {
    const h = await load();
    storage.failWrites = 2;
    h.add(entry("mem"));
    expect(h.get("mem")).toBeDefined();
  });

  it("notifies subscribers, including for changes from other tabs", async () => {
    const h = await load();
    const listener = vi.fn();
    const unsubscribe = h.subscribe(listener);
    h.add(entry("a"));
    expect(listener).toHaveBeenCalledTimes(1);

    storage.data.set("fg-history-v1", JSON.stringify([entry("other-tab")]));
    events.dispatchEvent(Object.assign(new Event("storage"), { key: "fg-history-v1" }));
    expect(listener).toHaveBeenCalledTimes(2);
    expect(h.get("other-tab")).toBeDefined();

    events.dispatchEvent(Object.assign(new Event("storage"), { key: "unrelated" }));
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    h.clear();
    expect(listener).toHaveBeenCalledTimes(2);
  });
});
