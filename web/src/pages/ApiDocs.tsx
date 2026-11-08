import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Badge, Card, PageHeader, cx } from "../components/ui";

interface Endpoint {
  id: string;
  method: "GET" | "POST";
  path: string;
  title: string;
  description: string;
  fields?: [string, string][];
  curl: string;
  response: string;
}

const ORIGIN = typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:8000";

const ENDPOINTS: Endpoint[] = [
  {
    id: "image",
    method: "POST",
    path: "/api/detect-image/",
    title: "Image tamper detection",
    description: "Level-1 metadata forensics plus Level-2 error-level analysis with a CNN.",
    fields: [["image", "Image file — jpg, jpeg, png or webp, up to 100 MB. The content must match the extension (415 otherwise)"]],
    curl: `curl -F "image=@photo.jpg" ${ORIGIN}/api/detect-image/`,
    response: `{
  "label": "UNVALIDATED",         // no verdict: the image model has not passed an evaluation
                                  // PNG/WebP: "UNSUPPORTED" (no score); validated model: AUTHENTIC/TAMPERED
  "predicted_class": -1,          // 0 tampered / 1 authentic only with a verdict
  "authentic_prob": 0.1584,       // experimental, uncalibrated score
  "tampered_prob": 0.8416,
  "confidence_pct": null,         // only given with a validated verdict
  "experimental": true,
  "reason": "This model has not passed a committed evaluation, so no verdict is given. ...",
  "device": "cuda",
  "level1": {
    "software_found": true,
    "software_signature": "Adobe Photoshop 25.0 (Windows)",
    "notes": ["Software signature found: Adobe Photoshop 25.0 (Windows)"]
  },
  "original_image": null,         // saved filename when the server keeps uploads
  "processing_time_ms": 461.6
}`,
  },
  {
    id: "video",
    method: "POST",
    path: "/api/detect-video/",
    title: "Video deepfake detection",
    description: "Samples 32 frames, extracts faces with MTCNN and classifies each with EfficientNet-B7.",
    fields: [["video", "Video file — mp4, avi, webm, mov, mkv, flv, 3gp, wmv or gif, up to 100 MB"]],
    curl: `curl -F "video=@clip.mp4" ${ORIGIN}/api/detect-video/`,
    response: `{
  "label": "FAKE",                // "REAL" | "FAKE" | "UNSURE" (no face found)
  "predicted_class": 0,           // 0 = fake, 1 = real, -1 = undecided
  "fake_prob": 0.987,
  "real_prob": 0.013,
  "confidence_pct": 98.7,
  "device": "cuda",
  "num_frames_sampled": 32,       // frames read from the video
  "num_faces_analyzed": 32,       // faces classified (= frame_predictions length)
  "frame_predictions": [0.98, 0.97, ...],   // per-face fake probability
  "processing_time_ms": 2154.2,
  "notes": [],                    // e.g. ["NO_FACE_DETECTED"]
  "status": "success"             // or "NO_FACE_DETECTED"
}`,
  },
  {
    id: "unified",
    method: "POST",
    path: "/api/detect/",
    title: "Unified detection",
    description: "Routes the file to the image or video model by its extension.",
    fields: [["file", "Image or video file, up to 100 MB"]],
    curl: `curl -F "file=@media.mp4" ${ORIGIN}/api/detect/`,
    response: `{
  "media_type": "video",          // or "image"
  "label": "REAL",
  "confidence_pct": 99.2,
  "device": "cpu",
  "processing_time_ms": 16627.4,
  // images: "level1" {...}, "level2" {authentic_prob, tampered_prob, method}
  // videos: "num_frames_sampled", "num_faces_analyzed", "frame_predictions", "notes"
  "status": "success"             // "error" (HTTP 422/500) with an "error" message on failure
}`,
  },
  {
    id: "batch",
    method: "POST",
    path: "/api/detect/batch",
    title: "Batch detection",
    description:
      "Queues one background job per file and waits up to 20 s for all of them. A batch still running after that returns 202 with a batch_id and a poll URL (see Jobs).",
    fields: [["file", "Repeated — one entry per image or video, up to 20 files"]],
    curl: `curl -F "file=@a.jpg" -F "file=@b.mp4" ${ORIGIN}/api/detect/batch`,
    response: `{
  "status": "partial_error",      // "success" | "partial_error" | "error"
  "results": [ { ...unified result, "file_index": 0, "file_name": "a.jpg" } ],
  "errors":  [ { "file_index": 1, "file_name": "b.mp4", "error": "..." } ],
  "num_success": 1,
  "num_errors": 1,
  "processing_time_ms": 18210.5
}`,
  },
  {
    id: "jobs",
    method: "POST",
    path: "/api/jobs/",
    title: "Submit a job",
    description:
      "Queues one file for analysis and returns immediately with a job id. The detect endpoints above use the same queue and return 202 with a job id when a job outlasts their 20 s wait. A full queue answers 503 BUSY at once.",
    fields: [
      ["file", "Image or video file"],
      ["kind", "Optional: image, video or unified (default: chosen from the extension)"],
    ],
    curl: `curl -F "file=@clip.mp4" ${ORIGIN}/api/jobs/`,
    response: `// 202 Accepted
{
  "job_id": "4f1c…",
  "status": "queued",
  "kind": "video",
  "poll": "/api/jobs/4f1c…/"
}`,
  },
  {
    id: "job-status",
    method: "GET",
    path: "/api/jobs/<id>/",
    title: "Poll a job",
    description:
      "Status is queued, running, done or failed. When finished, http_status and result are exactly what the synchronous endpoint would have returned. Batches work the same way at /api/batches/<id>/.",
    curl: `curl ${ORIGIN}/api/jobs/4f1c…/`,
    response: `{
  "job_id": "4f1c…",
  "status": "done",               // queued | running | done | failed
  "http_status": 200,
  "result": { ...same body as /api/detect-video/... },
  "created_at": 1794100000.1,
  "finished_at": 1794100023.4
}`,
  },
  {
    id: "health",
    method: "GET",
    path: "/api/health/",
    title: "Health check",
    description: "Model availability, compute device and upload limits. Returns 503 when a model is missing.",
    curl: `curl ${ORIGIN}/api/health/`,
    response: `{
  "status": "ok",                 // or "degraded"
  "device": "cuda",
  "gpu_name": "NVIDIA GeForce RTX 3060",
  "models": {
    "image": {"name": "IMDModel (ELA + CNN)", "file": "model_c1.pth", "present": true, "loaded": true, "size_mb": 56.6},
    "video": {"name": "EfficientNet-B7 + MTCNN", "file": "deepfake_detector_b7.pth", "present": true, "loaded": true, "size_mb": 254.5}
  },
  "limits": {"max_upload_mb": 100, "max_batch_files": 20, "image_extensions": [...], "video_extensions": [...], "video_frames_sampled": 32}
}`,
  },
];

const ERRORS: [string, string][] = [
  ["400", "Missing file, unsupported extension, file over the size limit, too many batch files, or unreadable media (status INVALID_IMAGE, INVALID_FILE, EMPTY_VIDEO, NO_VISUAL_FRAMES)."],
  ["404", "Unknown API path (JSON body, status NOT_FOUND)."],
  ["405", "Wrong HTTP method — detection endpoints accept POST only."],
  ["413", "Request body larger than the server accepts (status TOO_LARGE)."],
  ["422", "POST /api/detect/ only: the file was accepted but could not be analysed; the reason is in error."],
  ["429", "Rate limit reached (status RATE_LIMITED); wait for the Retry-After header's seconds."],
  ["500", "Inference failed on the server. Every response carries an X-Request-ID header to quote in bug reports."],
  ["503", "Model weights are missing (status model_not_found) or all inference slots are busy (status BUSY, with Retry-After)."],
];

function CodeBlock({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    // min-w-0: a grid item is otherwise as wide as its longest code line, which pushed
    // /docs 759 px past a phone screen (audit I20); the <pre> scrolls instead.
    <div className="relative min-w-0">
      <div className="flex items-center justify-between rounded-t-lg border border-b-0 border-line bg-surface-2 px-3 py-1.5">
        <span className="text-xs font-medium text-ink-3">{label}</span>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(code).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            });
          }}
          className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink"
          aria-label={`Copy ${label}`}
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {/* Focusable so keyboard users can scroll long lines (WCAG 2.1.1) */}
      <pre tabIndex={0} aria-label={`${label} example`} className="overflow-x-auto rounded-b-lg border border-line bg-surface p-4 font-mono text-[13px] leading-relaxed text-ink">{code}</pre>
    </div>
  );
}

export default function ApiDocs() {
  return (
    <>
      <PageHeader
        title="API reference"
        description="Every analysis in this app goes through these HTTP endpoints. Uploads use multipart/form-data; responses are JSON with an error message in the error field on failure."
      />
      <div className="grid gap-8 lg:grid-cols-[200px_1fr]">
        <nav className="hidden lg:block" aria-label="Endpoints">
          <ul className="sticky top-24 space-y-1 text-sm">
            {ENDPOINTS.map((e) => (
              <li key={e.id}>
                <a href={`#${e.id}`} className="block rounded-md px-2 py-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink">
                  {e.title}
                </a>
              </li>
            ))}
            <li>
              <a href="#errors" className="block rounded-md px-2 py-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink">
                Errors
              </a>
            </li>
          </ul>
        </nav>

        <div className="min-w-0 space-y-8">
          {ENDPOINTS.map((e) => (
            <Card key={e.id} className="scroll-mt-24 p-6" >
              <section id={e.id} className="scroll-mt-24">
                <div className="flex flex-wrap items-center gap-3">
                  <Badge tone={e.method === "GET" ? "good" : "accent"} className="font-mono">
                    {e.method}
                  </Badge>
                  <code className="font-mono text-sm font-semibold text-ink">{e.path}</code>
                </div>
                <h2 className="mt-3 text-lg font-semibold text-ink">{e.title}</h2>
                <p className="mt-1 text-sm text-ink-2">{e.description}</p>
                {e.fields && (
                  <div className="mt-4">
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">Form fields</h3>
                    <dl className="space-y-1 text-sm">
                      {e.fields.map(([k, v]) => (
                        <div key={k} className="flex gap-3">
                          <dt className="font-mono text-ink">{k}</dt>
                          <dd className="text-ink-2">{v}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
                <div className="mt-5 grid gap-4">
                  <CodeBlock label="Request" code={e.curl} />
                  <CodeBlock label="Response" code={e.response} />
                </div>
              </section>
            </Card>
          ))}

          <Card className="p-6">
            <section id="errors" className="scroll-mt-24">
              <h2 className="text-lg font-semibold text-ink">Errors</h2>
              <table className="mt-4 w-full text-sm">
                <tbody>
                  {ERRORS.map(([code, text], i) => (
                    <tr key={code} className={cx(i > 0 && "border-t border-line")}>
                      <td className="py-2.5 pr-4 align-top font-mono font-semibold text-ink">{code}</td>
                      <td className="py-2.5 text-ink-2">{text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </Card>
        </div>
      </div>
    </>
  );
}
