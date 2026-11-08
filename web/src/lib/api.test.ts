import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AbortedError, ApiError, detectBatch, detectImage, detectVideo, getHealth } from "./api";

// ── Stubs ────────────────────────────────────────────────────────────────────

let xhrReply: { status: number; body: unknown } = { status: 200, body: {} };

class FakeXHR {
  status = 0;
  responseText = "";
  responseType = "";
  upload: { onprogress?: (e: unknown) => void; onload?: () => void } = {};
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  open() {}
  abort() {
    this.onabort?.();
  }
  send() {
    queueMicrotask(() => {
      this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 });
      this.upload.onload?.();
      this.status = xhrReply.status;
      this.responseText = typeof xhrReply.body === "string" ? xhrReply.body : JSON.stringify(xhrReply.body);
      this.onload?.();
    });
  }
}

type Reply = { status: number; body: unknown } | "network-error";
let fetchReplies: Reply[] = [];
const fetchMock = vi.fn(async (..._args: unknown[]) => {
  const next = fetchReplies.shift() ?? { status: 500, body: null };
  if (next === "network-error") throw new TypeError("network down");
  return { ok: next.status >= 200 && next.status < 300, status: next.status, json: async () => next.body };
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockClear();
  fetchReplies = [];
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const file = { name: "a.jpg" } as File;
const pending = (kind: "job" | "batch") => ({
  status: 202,
  body: { status: "PENDING", [`${kind}_id`]: "x1", poll: `/api/${kind === "job" ? "jobs" : "batches"}/x1/` },
});

async function settle<T>(p: Promise<T>): Promise<T> {
  await vi.runAllTimersAsync();
  return p;
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("upload, then poll when the server answers 202", () => {
  it("returns a 200 result directly and reports progress", async () => {
    xhrReply = { status: 200, body: { label: "UNVALIDATED" } };
    const progress: number[] = [];
    const processing = vi.fn();
    const r = await settle(detectImage(file, { onUploadProgress: (p) => progress.push(p), onProcessing: processing }));
    expect(r).toEqual({ label: "UNVALIDATED" });
    expect(progress).toEqual([0.5, 1]);
    expect(processing).toHaveBeenCalledOnce();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("polls a job until it is done and returns its result", async () => {
    xhrReply = pending("job");
    fetchReplies = [
      { status: 200, body: { status: "queued", http_status: null, result: null } },
      { status: 200, body: { status: "running", http_status: null, result: null } },
      { status: 200, body: { status: "done", http_status: 200, result: { label: "FAKE" } } },
    ];
    expect(await settle(detectVideo(file))).toEqual({ label: "FAKE" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/jobs/x1/");
  });

  it("turns a failed job into an ApiError carrying the standard code", async () => {
    xhrReply = pending("job");
    fetchReplies = [
      { status: 200, body: { status: "failed", http_status: 400, result: { error: "bad", status: "INVALID_IMAGE", code: "INVALID_MEDIA" } } },
    ];
    const err = await settle(detectImage(file).catch((e) => e));
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ message: "bad", status: 400, code: "INVALID_MEDIA" });
  });

  it("polls a batch until it is no longer running", async () => {
    xhrReply = pending("batch");
    fetchReplies = [
      { status: 200, body: { status: "running", done: 1, total: 2 } },
      { status: 200, body: { status: "success", done: 2, total: 2, results: [], errors: [] } },
    ];
    const r = await settle(detectBatch([file, file]));
    expect(r).toMatchObject({ status: "success", done: 2 });
  });

  it("tolerates brief network errors while polling", async () => {
    xhrReply = pending("job");
    fetchReplies = ["network-error", "network-error",
      { status: 200, body: { status: "done", http_status: 200, result: { ok: true } } }];
    expect(await settle(detectVideo(file))).toEqual({ ok: true });
  });

  it("gives up after repeated network errors", async () => {
    xhrReply = pending("job");
    fetchReplies = Array(5).fill("network-error");
    const err = await settle(detectVideo(file).catch((e) => e));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });

  it("stops polling when cancelled", async () => {
    xhrReply = pending("job");
    fetchReplies = Array(50).fill({ status: 200, body: { status: "running", http_status: null, result: null } });
    const ctrl = new AbortController();
    const p = detectVideo(file, { signal: ctrl.signal }).catch((e) => e);
    await vi.advanceTimersByTimeAsync(2000);
    ctrl.abort();
    const err = await settle(p);
    expect(err).toBeInstanceOf(AbortedError);
  });

  it("reports an expired job (404) as an error", async () => {
    xhrReply = pending("job");
    fetchReplies = [{ status: 404, body: { error: "Job not found or expired.", status: "NOT_FOUND", code: "NOT_FOUND" } }];
    const err = await settle(detectVideo(file).catch((e) => e));
    expect(err).toMatchObject({ status: 404, code: "NOT_FOUND" });
  });
});

describe("upload errors", () => {
  it("uses the server's message and code", async () => {
    xhrReply = { status: 503, body: { error: "busy", status: "BUSY", code: "BUSY" } };
    const err = await settle(detectImage(file).catch((e) => e));
    expect(err).toMatchObject({ message: "busy", status: 503, code: "BUSY" });
  });

  it("falls back to a generic message for non-JSON errors", async () => {
    xhrReply = { status: 502, body: "<html>bad gateway</html>" };
    const err = await settle(detectImage(file).catch((e) => e));
    expect(err.message).toMatch(/HTTP 502/);
  });
});

describe("health", () => {
  it("returns the body even when degraded (503)", async () => {
    fetchReplies = [{ status: 503, body: { status: "degraded", models: {} } }];
    expect(await getHealth()).toMatchObject({ status: "degraded" });
  });

  it("reports an unreachable server", async () => {
    fetchReplies = ["network-error"];
    const err = await getHealth().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });
});
