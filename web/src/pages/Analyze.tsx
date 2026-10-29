import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Download, FileImage, FileVideo, History, Printer, RotateCcw, ScanSearch, X } from "lucide-react";
import Dropzone from "../components/Dropzone";
import ReportView from "../components/ReportView";
import { Button, Card, PageHeader, cx } from "../components/ui";
import { useHealth } from "../hooks/useHealth";
import { AbortedError, ApiError, detectImage, detectVideo } from "../lib/api";
import { fromImageResponse, fromVideoResponse, mediaTypeFor, validateFile } from "../lib/analysis";
import { downloadJson } from "../lib/download";
import { formatBytes, formatDuration } from "../lib/format";
import { handOffFile, takeHandedOffFile } from "../lib/handoff";
import { history } from "../lib/history";
import { makeThumbnail } from "../lib/thumbnail";
import type { Analysis, MediaType } from "../lib/types";

type Phase =
  | { name: "idle" }
  | { name: "selected" }
  | { name: "uploading"; progress: number }
  | { name: "processing"; startedAt: number }
  | { name: "done"; analysis: Analysis }
  | { name: "error"; message: string };

const PIPELINE: Record<MediaType, string[]> = {
  image: [
    "Scan metadata for editing-software signatures",
    "Re-compress and compute the error-level map",
    "Classify the error map with the CNN",
  ],
  video: [
    "Sample frames evenly across the video",
    "Detect and crop faces with MTCNN",
    "Classify each face with EfficientNet-B7",
    "Aggregate face scores into a verdict",
  ],
};

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);
  return <span className="tabular">{formatDuration(now - since)}</span>;
}

export default function Analyze() {
  const { limits, health } = useHealth();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [phase, setPhase] = useState<Phase>({ name: "idle" });
  const [validation, setValidation] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const mediaType = file ? mediaTypeFor(file.name, limits) : null;

  const reset = useCallback(() => {
    abort.current?.abort();
    setFile(null);
    setValidation(null);
    setPhase({ name: "idle" });
  }, []);

  const choose = useCallback(
    (f: File) => {
      abort.current?.abort();
      setFile(f);
      setValidation(validateFile(f, limits));
      setPhase({ name: "selected" });
    },
    [limits],
  );

  // Object URL lifecycle follows the selected file
  useEffect(() => {
    if (!file) return setPreviewUrl(undefined);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const run = useCallback(
    async (f: File) => {
      const type = mediaTypeFor(f.name, limits);
      if (!type) return;
      const ctrl = new AbortController();
      abort.current = ctrl;
      setPhase({ name: "uploading", progress: 0 });

      const thumbnail = makeThumbnail(f);
      const cb = {
        signal: ctrl.signal,
        onUploadProgress: (p: number) => setPhase((ph) => (ph.name === "uploading" ? { name: "uploading", progress: p } : ph)),
        onProcessing: () => setPhase({ name: "processing", startedAt: Date.now() }),
      };

      try {
        const meta = { fileName: f.name, fileSize: f.size, thumbnail: await thumbnail };
        const analysis =
          type === "image" ? fromImageResponse(await detectImage(f, cb), meta) : fromVideoResponse(await detectVideo(f, cb), meta);
        history.add(analysis);
        setPhase({ name: "done", analysis });
      } catch (e) {
        if (e instanceof AbortedError) return;
        setPhase({ name: "error", message: e instanceof ApiError ? e.message : "Something went wrong while analyzing the file." });
      }
    },
    [limits],
  );

  // Pick up a file dropped on the Home page and start right away
  useEffect(() => {
    const handoff = takeHandedOffFile();
    if (handoff) {
      const f = handoff.file;
      const err = validateFile(f, limits);
      setFile(f);
      setValidation(err);
      if (err) setPhase({ name: "selected" });
      else void run(f);
    }
    return () => {
      abort.current?.abort();
      // Strict Mode remounts immediately; give the remount the same file back
      if (handoff) handOffFile(handoff.file, handoff.at);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (phase.name === "done") {
    const a = phase.analysis;
    return (
      <>
        <div className="no-print">
          <PageHeader title="Analysis report" description={`Results for ${a.fileName}`} />
        </div>
        <ReportView
          analysis={a}
          previewUrl={previewUrl}
          actions={
            <>
              <Button onClick={reset}>
                <ScanSearch className="size-4" /> Analyze another file
              </Button>
              <Button variant="secondary" onClick={() => window.print()}>
                <Printer className="size-4" /> Print / Save PDF
              </Button>
              <Button variant="secondary" onClick={() => downloadJson(a)}>
                <Download className="size-4" /> Export JSON
              </Button>
              <Link to="/history" className="ml-auto inline-flex items-center gap-1.5 self-center text-sm text-ink-2 hover:text-ink">
                <History className="size-4" /> Saved to history
              </Link>
            </>
          }
        />
      </>
    );
  }

  const busy = phase.name === "uploading" || phase.name === "processing";
  const offline = health.state === "offline";

  return (
    <>
      <PageHeader
        title="Analyze media"
        description="Upload an image to check for tampering, or a video to check for face deepfakes. The right model is chosen from the file type."
      />

      {offline && (
        <div className="mb-6 flex gap-3 rounded-xl bg-critical-soft p-4 text-sm text-critical-ink">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-semibold">The ForgeGuard backend is not reachable</p>
            <p className="opacity-90">
              Start it with <code className="font-mono">python manage.py runserver</code>, then retry. You can still pick a file.
            </p>
          </div>
        </div>
      )}

      {!file ? (
        <Dropzone
          onFiles={([f]) => choose(f)}
          extensions={[...limits.image_extensions, ...limits.video_extensions]}
          maxMb={limits.max_upload_mb}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          <Card className="overflow-hidden lg:col-span-3">
            <div className="relative grid aspect-video place-items-center overflow-hidden bg-surface-2 [&>img]:absolute [&>img]:inset-0 [&>video]:absolute [&>video]:inset-0">
              {previewUrl && mediaType === "video" ? (
                <video src={previewUrl} controls muted playsInline className="h-full w-full bg-black object-contain" />
              ) : previewUrl && mediaType === "image" ? (
                <img src={previewUrl} alt="Selected file preview" className="h-full w-full object-contain" />
              ) : (
                <FileImage className="size-10 text-ink-3" />
              )}
            </div>
            <div className="flex items-center gap-3 p-4">
              <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-surface-2 text-ink-2">
                {mediaType === "video" ? <FileVideo className="size-5" /> : <FileImage className="size-5" />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink" title={file.name}>
                  {file.name}
                </p>
                <p className="text-xs text-ink-3">
                  {formatBytes(file.size)} · {mediaType === "video" ? "Video — deepfake detection" : mediaType === "image" ? "Image — tamper detection" : "Unsupported type"}
                </p>
              </div>
              {!busy && (
                <button onClick={reset} className="grid size-8 place-items-center rounded-lg text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label="Remove file">
                  <X className="size-4" />
                </button>
              )}
            </div>
          </Card>

          <Card className="flex flex-col p-6 lg:col-span-2">
            {validation ? (
              <>
                <div className="flex gap-3 rounded-xl bg-critical-soft p-4 text-sm text-critical-ink">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" />
                  <p>{validation}</p>
                </div>
                <Button variant="secondary" className="mt-auto" onClick={reset}>
                  Choose another file
                </Button>
              </>
            ) : phase.name === "selected" ? (
              <>
                <h2 className="font-semibold text-ink">Ready to analyze</h2>
                <p className="mt-1 text-sm text-ink-2">The pipeline will:</p>
                <ol className="mt-3 space-y-2 text-sm text-ink-2">
                  {PIPELINE[mediaType!].map((s, i) => (
                    <li key={s} className="flex gap-3">
                      <span className="grid size-5 shrink-0 place-items-center rounded-full bg-surface-2 text-xs font-medium text-ink-2 tabular">{i + 1}</span>
                      {s}
                    </li>
                  ))}
                </ol>
                {mediaType === "video" && (
                  <p className="mt-4 text-xs text-ink-3">
                    Video analysis takes roughly 15–60 seconds on {health.data?.device === "cuda" ? "GPU" : "CPU"}.
                  </p>
                )}
                <div className="mt-6 flex gap-2 lg:mt-auto lg:pt-6">
                  <Button size="lg" className="flex-1" onClick={() => run(file)}>
                    <ScanSearch className="size-4.5" /> Analyze
                  </Button>
                  <Button size="lg" variant="secondary" onClick={reset}>
                    Cancel
                  </Button>
                </div>
              </>
            ) : busy ? (
              <div aria-live="polite">
                <h2 className="font-semibold text-ink">{phase.name === "uploading" ? "Uploading…" : "Analyzing…"}</h2>
                <p className="mt-1 text-sm text-ink-2">
                  {phase.name === "uploading" ? (
                    <span className="tabular">{Math.round(phase.progress * 100)}% of {formatBytes(file.size)}</span>
                  ) : (
                    <>
                      Running the {mediaType} pipeline · <Elapsed since={phase.startedAt} />
                    </>
                  )}
                </p>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-2">
                  {phase.name === "uploading" ? (
                    <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${phase.progress * 100}%` }} />
                  ) : (
                    <div className="fg-indeterminate h-full w-2/5 rounded-full bg-accent" />
                  )}
                </div>
                <ol className="mt-6 space-y-2 text-sm text-ink-3">
                  {PIPELINE[mediaType!].map((s) => (
                    <li key={s} className={cx("flex gap-3", phase.name === "processing" && "text-ink-2")}>
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-current" />
                      {s}
                    </li>
                  ))}
                </ol>
                <Button variant="secondary" className="mt-6 w-full" onClick={() => { abort.current?.abort(); setPhase({ name: "selected" }); }}>
                  Cancel
                </Button>
              </div>
            ) : phase.name === "error" ? (
              <>
                <div className="flex gap-3 rounded-xl bg-critical-soft p-4 text-sm text-critical-ink" role="alert">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" />
                  <div>
                    <p className="font-semibold">Analysis failed</p>
                    <p className="mt-0.5 opacity-90">{phase.message}</p>
                  </div>
                </div>
                <div className="mt-6 flex gap-2 lg:mt-auto lg:pt-6">
                  <Button className="flex-1" onClick={() => run(file)}>
                    <RotateCcw className="size-4" /> Retry
                  </Button>
                  <Button variant="secondary" onClick={reset}>
                    Choose another
                  </Button>
                </div>
              </>
            ) : null}
          </Card>
        </div>
      )}
    </>
  );
}
