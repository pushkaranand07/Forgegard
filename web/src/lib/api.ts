import type {
  BatchApiResponse,
  HealthResponse,
  ImageApiResponse,
  VideoApiResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export class AbortedError extends Error {
  constructor() {
    super("Upload cancelled");
    this.name = "AbortedError";
  }
}

export interface UploadCallbacks {
  /** 0–1 fraction of the request body sent */
  onUploadProgress?: (fraction: number) => void;
  /** Fired once the body is fully sent and the server is running inference */
  onProcessing?: () => void;
  signal?: AbortSignal;
}

function messageFor(status: number, body: unknown): string {
  if (body && typeof body === "object" && "error" in body && typeof body.error === "string") {
    return body.error;
  }
  if (status === 0) return "Could not reach the ForgeGuard server. Check that the backend is running.";
  if (status === 413) return "The file is larger than the server accepts.";
  if (status >= 500) return `The server failed to process the file (HTTP ${status}).`;
  return `Request failed (HTTP ${status}).`;
}

/** A 202 from a detection endpoint: the analysis continues as a background job. */
interface PendingBody {
  status: "PENDING";
  poll: string;
  job_id?: string;
  batch_id?: string;
}

function isPending(body: unknown): body is PendingBody {
  return !!body && typeof body === "object" && "poll" in body && typeof (body as PendingBody).poll === "string";
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => { clearTimeout(t); reject(new AbortedError()); }, { once: true });
  });

/**
 * Poll /api/jobs/<id>/ or /api/batches/<id>/ until the work is finished, then
 * return what the synchronous endpoint would have returned.
 */
async function pollUntilDone<T>(pending: PendingBody, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE}${pending.poll}`;
  let delay = 700;
  let networkFailures = 0;
  for (;;) {
    if (signal?.aborted) throw new AbortedError();
    await sleep(delay, signal);
    delay = Math.min(delay * 1.3, 2500);

    let res: Response;
    try {
      res = await fetch(url, { signal, headers: { Accept: "application/json" } });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw new AbortedError();
      if (++networkFailures >= 5) throw new ApiError(messageFor(0, null), 0);
      continue;
    }
    networkFailures = 0;
    const body: unknown = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(messageFor(res.status, body), res.status, codeOf(body));
    if (!body || typeof body !== "object") continue;

    if (pending.batch_id) {
      const batch = body as { status: string };
      if (batch.status !== "running") return body as T;
      continue;
    }
    const job = body as { status: string; http_status: number | null; result: unknown };
    if (job.status === "done" || job.status === "failed") {
      const status = job.http_status ?? 500;
      if (status >= 200 && status < 300) return job.result as T;
      throw new ApiError(messageFor(status, job.result), status, codeOf(job.result));
    }
  }
}

function codeOf(body: unknown): string | undefined {
  return body && typeof body === "object" && "status" in body && typeof body.status === "string"
    ? body.status
    : undefined;
}

/** multipart POST via XHR — fetch() cannot report upload progress. A 202 is followed by polling. */
function postForm<T>(url: string, form: FormData, cb: UploadCallbacks = {}): Promise<T> {
  return postFormOnce<T | PendingBody>(url, form, cb).then((body) =>
    isPending(body) ? pollUntilDone<T>(body, cb.signal) : (body as T),
  );
}

function postFormOnce<T>(url: string, form: FormData, cb: UploadCallbacks = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "text";

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) cb.onUploadProgress?.(e.loaded / e.total);
    };
    xhr.upload.onload = () => {
      cb.onUploadProgress?.(1);
      cb.onProcessing?.();
    };

    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // Non-JSON (e.g. proxy error page) — handled below
      }
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        resolve(body as T);
      } else {
        const code =
          body && typeof body === "object" && "status" in body && typeof body.status === "string"
            ? body.status
            : undefined;
        reject(new ApiError(messageFor(xhr.status, body), xhr.status, code));
      }
    };
    xhr.onerror = () => reject(new ApiError(messageFor(0, null), 0));
    xhr.onabort = () => reject(new AbortedError());

    if (cb.signal) {
      if (cb.signal.aborted) return reject(new AbortedError());
      cb.signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    xhr.send(form);
  });
}

const API_BASE = (
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  (import.meta.env.VITE_API_URL as string | undefined) ||
  ""
).replace(/\/+$/, "");

export function detectImage(file: File, cb?: UploadCallbacks) {
  const form = new FormData();
  form.append("image", file);
  return postForm<ImageApiResponse>(`${API_BASE}/api/detect-image/`, form, cb);
}

export function detectVideo(file: File, cb?: UploadCallbacks) {
  const form = new FormData();
  form.append("video", file);
  return postForm<VideoApiResponse>(`${API_BASE}/api/detect-video/`, form, cb);
}

export function detectBatch(files: File[], cb?: UploadCallbacks) {
  const form = new FormData();
  for (const f of files) form.append("file", f);
  return postForm<BatchApiResponse>(`${API_BASE}/api/detect/batch`, form, cb);
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/health/`, { signal, headers: { Accept: "application/json" } });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw new AbortedError();
    throw new ApiError(messageFor(0, null), 0);
  }
  // 503 still carries a full health body (status: "degraded")
  const body = await res.json().catch(() => null);
  if (!body || !("models" in body)) throw new ApiError(messageFor(res.status, body), res.status);
  return body as HealthResponse;
}
