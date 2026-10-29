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

/** multipart POST via XHR — fetch() cannot report upload progress. */
function postForm<T>(url: string, form: FormData, cb: UploadCallbacks = {}): Promise<T> {
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

export function detectImage(file: File, cb?: UploadCallbacks) {
  const form = new FormData();
  form.append("image", file);
  return postForm<ImageApiResponse>("/api/detect-image/", form, cb);
}

export function detectVideo(file: File, cb?: UploadCallbacks) {
  const form = new FormData();
  form.append("video", file);
  return postForm<VideoApiResponse>("/api/detect-video/", form, cb);
}

export function detectBatch(files: File[], cb?: UploadCallbacks) {
  const form = new FormData();
  for (const f of files) form.append("file", f);
  return postForm<BatchApiResponse>("/api/detect/batch", form, cb);
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  let res: Response;
  try {
    res = await fetch("/api/health/", { signal, headers: { Accept: "application/json" } });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw new AbortedError();
    throw new ApiError(messageFor(0, null), 0);
  }
  // 503 still carries a full health body (status: "degraded")
  const body = await res.json().catch(() => null);
  if (!body || !("models" in body)) throw new ApiError(messageFor(res.status, body), res.status);
  return body as HealthResponse;
}
