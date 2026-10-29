import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Download, FileImage, FileSpreadsheet, FileVideo, Play, RotateCcw, Trash2, X } from "lucide-react";
import Dropzone from "../components/Dropzone";
import { Badge, Button, Card, PageHeader, cx } from "../components/ui";
import { useHealth } from "../hooks/useHealth";
import { AbortedError, ApiError, detectBatch } from "../lib/api";
import { errorAnalysis, fromUnifiedResult, mediaTypeFor } from "../lib/analysis";
import { downloadCsv, downloadJson } from "../lib/download";
import { formatBytes, formatConfidence, formatDuration } from "../lib/format";
import { history } from "../lib/history";
import { makeThumbnail } from "../lib/thumbnail";
import type { Analysis, MediaType } from "../lib/types";
import { verdictMeta } from "../lib/verdict";


interface Item {
  key: string;
  file: File;
  type: MediaType | null;
  problem: string | null;
}

type Phase =
  | { name: "idle" }
  | { name: "uploading"; progress: number }
  | { name: "processing"; startedAt: number }
  | { name: "done"; results: Analysis[]; totalMs: number }
  | { name: "error"; message: string };

export default function Batch() {
  const { limits } = useHealth();
  const [items, setItems] = useState<Item[]>([]);
  const [phase, setPhase] = useState<Phase>({ name: "idle" });
  const abort = useRef<AbortController | null>(null);

  const maxBytes = limits.max_upload_mb * 1024 * 1024;
  const maxFiles = limits.max_batch_files;
  const valid = items.filter((i) => !i.problem);
  const totalSize = valid.reduce((s, i) => s + i.file.size, 0);
  const busy = phase.name === "uploading" || phase.name === "processing";

  const add = (files: File[]) => {
    setPhase((p) => (p.name === "done" || p.name === "error" ? { name: "idle" } : p));
    setItems((prev) => {
      const next = [...prev];
      for (const file of files) {
        if (next.length >= maxFiles) break;
        if (next.some((i) => i.file.name === file.name && i.file.size === file.size)) continue;
        const type = mediaTypeFor(file.name, limits);
        const problem = !type
          ? "Unsupported type"
          : file.size === 0
            ? "Empty file"
            : file.size > maxBytes
              ? `Over ${limits.max_upload_mb} MB`
              : null;
        next.push({ key: `${file.name}-${file.size}-${file.lastModified}`, file, type, problem });
      }
      return next;
    });
  };

  const run = async () => {
    const files = valid.map((i) => i.file);
    if (!files.length) return;
    const ctrl = new AbortController();
    abort.current = ctrl;
    setPhase({ name: "uploading", progress: 0 });
    const thumbs = Promise.all(files.map(makeThumbnail));

    try {
      const res = await detectBatch(files, {
        signal: ctrl.signal,
        onUploadProgress: (p) => setPhase((ph) => (ph.name === "uploading" ? { name: "uploading", progress: p } : ph)),
        onProcessing: () => setPhase({ name: "processing", startedAt: Date.now() }),
      });
      const thumbnails = await thumbs;
      const results = files.map((f, idx): Analysis => {
        const meta = { fileName: f.name, fileSize: f.size, thumbnail: thumbnails[idx], source: "batch" as const };
        const ok = res.results.find((r) => r.file_index === idx);
        if (ok) return fromUnifiedResult(ok, meta);
        const err = res.errors.find((e) => e.file_index === idx);
        return errorAnalysis({ ...meta, mediaType: mediaTypeFor(f.name, limits) ?? "image" }, err?.error ?? "No result returned");
      });
      history.add(...results.filter((r) => r.verdict !== "error").reverse());
      setPhase({ name: "done", results, totalMs: res.processing_time_ms });
    } catch (e) {
      if (e instanceof AbortedError) return;
      setPhase({ name: "error", message: e instanceof ApiError ? e.message : "The batch request failed." });
    }
  };

  const summary = useMemo(() => {
    if (phase.name !== "done") return null;
    const c = { authentic: 0, manipulated: 0, inconclusive: 0, error: 0 };
    phase.results.forEach((r) => c[r.verdict]++);
    return c;
  }, [phase]);

  return (
    <>
      <PageHeader
        title="Batch analysis"
        description={`Screen up to ${maxFiles} images and videos in one run. Files are analyzed one after another on the server, so large video batches can take several minutes.`}
        actions={
          phase.name === "done" && (
            <>
              <Button variant="secondary" onClick={() => downloadCsv(phase.results)}>
                <FileSpreadsheet className="size-4" /> Export CSV
              </Button>
              <Button variant="secondary" onClick={() => downloadJson(phase.results)}>
                <Download className="size-4" /> Export JSON
              </Button>
            </>
          )
        }
      />

      {phase.name === "done" && summary ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {(
              [
                ["Authentic / real", summary.authentic, "good"],
                ["Manipulated", summary.manipulated, "critical"],
                ["Inconclusive", summary.inconclusive, "warning"],
                ["Failed", summary.error, "neutral"],
              ] as const
            ).map(([label, n, tone]) => (
              <Card key={label} className="p-5">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-3">{label}</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold text-ink tabular">
                  <span className={cx("size-2.5 rounded-full", { good: "bg-good", critical: "bg-critical", warning: "bg-warning", neutral: "bg-ink-3" }[tone])} aria-hidden />
                  {n}
                </p>
              </Card>
            ))}
          </div>

          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="bg-surface-2 text-left text-xs text-ink-3">
                  <tr>
                    <th className="px-4 py-3 font-medium">File</th>
                    <th className="px-4 py-3 font-medium">Verdict</th>
                    <th className="px-4 py-3 text-right font-medium">Confidence</th>
                    <th className="px-4 py-3 font-medium">Details</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {phase.results.map((r) => {
                    const v = verdictMeta(r);
                    const Icon = v.icon;
                    return (
                      <tr key={r.id} className="border-t border-line align-middle">
                        <td className="max-w-64 px-4 py-3">
                          <div className="flex items-center gap-3">
                            {r.mediaType === "video" ? <FileVideo className="size-4 shrink-0 text-ink-3" /> : <FileImage className="size-4 shrink-0 text-ink-3" />}
                            <span className="truncate text-ink" title={r.fileName}>{r.fileName}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge tone={v.tone}>
                            <Icon className="size-3" aria-hidden />
                            {v.short}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right text-ink tabular">
                          {r.verdict === "authentic" || r.verdict === "manipulated" ? formatConfidence(r.confidencePct) : "—"}
                        </td>
                        <td className="px-4 py-3 text-ink-2">
                          {r.error
                            ? r.error
                            : r.image?.softwareFound
                              ? `Metadata: ${r.image.softwareSignature}`
                              : r.video
                                ? r.video.notes.includes("NO_FACE_DETECTED")
                                  ? "No face detected"
                                  : `${r.video.framePredictions.length} faces analyzed`
                                : "Metadata clean"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {r.verdict !== "error" && (
                            <Link to={`/report/${r.id}`} className="font-medium text-accent hover:underline">
                              Report
                            </Link>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="border-t border-line px-4 py-3 text-xs text-ink-3">
              Completed in {formatDuration(phase.totalMs)}. Successful results were saved to History.
            </div>
          </Card>

          <Button
            variant="secondary"
            onClick={() => {
              setItems([]);
              setPhase({ name: "idle" });
            }}
          >
            <RotateCcw className="size-4" /> New batch
          </Button>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <Dropzone onFiles={add} extensions={[...limits.image_extensions, ...limits.video_extensions]} maxMb={limits.max_upload_mb} multiple disabled={busy || items.length >= maxFiles} compact={items.length > 0} />
            {items.length > 0 && (
              <Card className="mt-4 divide-y divide-line">
                {items.map((i) => (
                  <div key={i.key} className="flex items-center gap-3 px-4 py-3">
                    {i.type === "video" ? <FileVideo className="size-4 shrink-0 text-ink-3" /> : <FileImage className="size-4 shrink-0 text-ink-3" />}
                    <span className="min-w-0 flex-1 truncate text-sm text-ink" title={i.file.name}>{i.file.name}</span>
                    {i.problem ? <Badge tone="critical">{i.problem}</Badge> : <span className="text-xs text-ink-3 tabular">{formatBytes(i.file.size)}</span>}
                    {!busy && (
                      <button
                        onClick={() => setItems((prev) => prev.filter((p) => p.key !== i.key))}
                        className="grid size-7 place-items-center rounded-md text-ink-3 hover:bg-surface-2 hover:text-ink"
                        aria-label={`Remove ${i.file.name}`}
                      >
                        <X className="size-4" />
                      </button>
                    )}
                  </div>
                ))}
              </Card>
            )}
          </div>

          <Card className="h-fit p-6 lg:col-span-2">
            <h2 className="font-semibold text-ink">Queue</h2>
            <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-xs text-ink-3">Ready</dt>
                <dd className="text-lg font-semibold text-ink tabular">{valid.length} / {maxFiles}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-3">Total size</dt>
                <dd className="text-lg font-semibold text-ink tabular">{formatBytes(totalSize)}</dd>
              </div>
            </dl>

            {phase.name === "error" && (
              <div className="mt-4 flex gap-3 rounded-xl bg-critical-soft p-4 text-sm text-critical-ink" role="alert">
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                <p>{phase.message}</p>
              </div>
            )}

            {busy ? (
              <div className="mt-6" aria-live="polite">
                <p className="text-sm text-ink-2">
                  {phase.name === "uploading" ? `Uploading · ${Math.round(phase.progress * 100)}%` : `Analyzing ${valid.length} files…`}
                </p>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2">
                  {phase.name === "uploading" ? (
                    <div className="h-full rounded-full bg-accent" style={{ width: `${phase.progress * 100}%` }} />
                  ) : (
                    <div className="fg-indeterminate h-full w-2/5 rounded-full bg-accent" />
                  )}
                </div>
                <Button variant="secondary" className="mt-4 w-full" onClick={() => { abort.current?.abort(); setPhase({ name: "idle" }); }}>
                  Cancel
                </Button>
              </div>
            ) : (
              <div className="mt-6 flex gap-2">
                <Button className="flex-1" disabled={!valid.length} onClick={run}>
                  <Play className="size-4" /> Analyze {valid.length || ""} {valid.length === 1 ? "file" : "files"}
                </Button>
                {items.length > 0 && (
                  <Button variant="secondary" onClick={() => setItems([])} aria-label="Clear queue">
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>
            )}
            {items.some((i) => i.problem) && !busy && (
              <p className="mt-3 text-xs text-ink-3">Files marked in red will be skipped.</p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
