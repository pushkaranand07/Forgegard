import type { ReactNode } from "react";
import { AlertTriangle, FileImage, FileVideo, Info, ScanSearch, Tags } from "lucide-react";
import { noFaceDetected } from "../lib/analysis";
import { formatBytes, formatConfidence, formatDateTime, formatDuration, shortId } from "../lib/format";
import type { Analysis } from "../lib/types";
import { verdictMeta } from "../lib/verdict";
import FrameChart from "./FrameChart";
import ProbabilityBar from "./ProbabilityBar";
import { Badge, Card, Stat, cx } from "./ui";

const toneRing: Record<string, string> = {
  good: "var(--good)",
  critical: "var(--critical)",
  warning: "var(--warning)",
  neutral: "var(--text-3)",
  accent: "var(--accent)",
};

const toneBg: Record<string, string> = {
  good: "bg-good-soft text-good-ink",
  critical: "bg-critical-soft text-critical-ink",
  warning: "bg-warning-soft text-warning-ink",
  neutral: "bg-surface-2 text-ink-2",
  accent: "bg-accent-soft text-accent",
};

function ConfidenceRing({ pct, tone }: { pct: number | null; tone: string }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative size-24 shrink-0">
      <svg viewBox="0 0 80 80" className="size-24 -rotate-90" aria-hidden>
        <circle cx="40" cy="40" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="6" />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke={toneRing[tone]}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${((pct ?? 0) / 100) * c} ${c}`}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="text-lg font-bold leading-none text-ink tabular">{formatConfidence(pct)}</div>
          <div className="mt-1 text-[10px] font-medium uppercase tracking-wide text-ink-3">model score</div>
        </div>
      </div>
    </div>
  );
}

function Section({ icon, title, children, className }: { icon: ReactNode; title: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cx("p-5 sm:p-6 print-avoid-break", className)}>
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-ink">
        <span className="text-ink-3">{icon}</span>
        {title}
      </h3>
      {children}
    </Card>
  );
}

function Callout({ tone, title, children }: { tone: "warning" | "neutral" | "critical"; title: string; children: ReactNode }) {
  return (
    <div className={cx("flex gap-3 rounded-xl p-4 text-sm", toneBg[tone])}>
      {tone === "neutral" ? <Info className="mt-0.5 size-4 shrink-0" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0" />}
      <div>
        <p className="font-semibold">{title}</p>
        <div className="mt-0.5 opacity-90">{children}</div>
      </div>
    </div>
  );
}

interface Props {
  analysis: Analysis;
  /** Object URL of the original file, available right after upload */
  previewUrl?: string;
  actions?: ReactNode;
}

export default function ReportView({ analysis: a, previewUrl, actions }: Props) {
  const v = verdictMeta(a);
  const Icon = v.icon;
  const isVideo = a.mediaType === "video";
  const metaWarning = a.image?.softwareFound;

  return (
    <article className="space-y-6">
      {/* Printed reports get a document header instead of the app chrome */}
      <header className="print-only mb-6 border-b border-line pb-4">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">ForgeGuard</p>
            <h1 className="text-2xl font-semibold text-ink">Media Forensic Report</h1>
          </div>
          <div className="text-right text-xs text-ink-2">
            <p>Report {shortId(a.id)}</p>
            <p>Analyzed {formatDateTime(a.createdAt)}</p>
            <p>Printed {formatDateTime(new Date().toISOString())}</p>
          </div>
        </div>
      </header>

      {/* Verdict */}
      <Card className="overflow-hidden print-avoid-break">
        <div className={cx("h-1.5", { good: "bg-good", critical: "bg-critical", warning: "bg-warning" }[v.tone as string] ?? "bg-line")} />
        <div className="flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:p-8">
          <div className={cx("grid size-14 shrink-0 place-items-center rounded-2xl", toneBg[v.tone])}>
            <Icon className="size-7" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge tone={v.tone}>
                <Icon className="size-3" aria-hidden />
                {v.short}
              </Badge>
              <Badge>{isVideo ? "Video" : "Image"}</Badge>
              {metaWarning && (
                <Badge tone="warning">
                  <Tags className="size-3" aria-hidden />
                  Editing software in metadata
                </Badge>
              )}
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{v.title}</h2>
            <p className="mt-2 max-w-2xl text-ink-2">{v.summary}</p>
          </div>
          {a.verdict === "authentic" || a.verdict === "manipulated" ? (
            <ConfidenceRing pct={a.confidencePct} tone={v.tone} />
          ) : null}
        </div>
        {actions && <div className="flex flex-wrap gap-2 border-t border-line px-6 py-4 sm:px-8 no-print">{actions}</div>}
      </Card>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Media + file facts */}
        <div className="space-y-6 lg:col-span-2">
          <Card className="overflow-hidden print-avoid-break">
            <div className="relative grid aspect-video place-items-center overflow-hidden bg-surface-2 [&>img]:absolute [&>img]:inset-0 [&>video]:absolute [&>video]:inset-0">
              {previewUrl && isVideo ? (
                <video src={previewUrl} controls muted playsInline className="h-full w-full bg-black object-contain no-print" />
              ) : previewUrl ? (
                <img src={previewUrl} alt={a.fileName} className="h-full w-full object-contain" />
              ) : a.thumbnail ? (
                <img src={a.thumbnail} alt={a.fileName} className="h-full w-full object-contain" />
              ) : isVideo ? (
                <FileVideo className="size-10 text-ink-3" aria-hidden />
              ) : (
                <FileImage className="size-10 text-ink-3" aria-hidden />
              )}
              {/* Printing a <video> yields a blank box — print the poster frame instead */}
              {previewUrl && isVideo &&
                (a.thumbnail ? (
                  <img src={a.thumbnail} alt="" className="print-only h-full w-full object-contain" />
                ) : (
                  <span className="print-only">
                    <FileVideo className="size-10 text-ink-3" aria-hidden />
                  </span>
                ))}
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-4 p-5">
              <div className="col-span-2">
                <Stat label="File" value={<span title={a.fileName}>{a.fileName}</span>} />
              </div>
              <Stat label="Size" value={formatBytes(a.fileSize)} />
              <Stat label="Type" value={isVideo ? "Video" : "Image"} />
              <Stat label="Analyzed" value={formatDateTime(a.createdAt)} />
              <Stat label="Report ID" value={<span className="font-mono">{shortId(a.id)}</span>} />
              <Stat label="Compute" value={a.device.toUpperCase()} />
              <Stat label="Processing" value={formatDuration(a.processingMs)} />
            </dl>
          </Card>
        </div>

        {/* Findings */}
        <div className="space-y-6 lg:col-span-3">
          {a.verdict === "error" && (
            <Callout tone="critical" title="The analysis did not complete">
              {a.error ?? "Unknown error."} Try again, or check the System page to confirm the models are loaded.
            </Callout>
          )}

          {a.image && (
            <Section icon={<Tags className="size-4" />} title="Level 1 · Metadata forensics">
              {a.image.softwareFound ? (
                <Callout tone="warning" title="Editing software signature found">
                  The file's metadata names <strong className="font-semibold">{a.image.softwareSignature}</strong>. This
                  shows the image passed through editing software — it does not by itself prove the content was altered.
                </Callout>
              ) : (
                <p className="text-sm text-ink-2">No editing-software signature was found in the file's metadata.</p>
              )}
              {a.image.notes.length > 0 && (
                <ul className="mt-4 space-y-1.5 text-sm text-ink-2">
                  {a.image.notes.map((n) => (
                    <li key={n} className="flex gap-2">
                      <span className="mt-2 size-1 shrink-0 rounded-full bg-ink-3" aria-hidden />
                      {n}
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}

          {a.probs && (
            <Section
              icon={<ScanSearch className="size-4" />}
              title={isVideo ? "Deepfake classifier · EfficientNet-B7" : `Level 2 · ${a.image?.method ?? "ELA + CNN"}`}
            >
              <ProbabilityBar
                authentic={a.probs.authentic}
                manipulated={a.probs.manipulated}
                authenticLabel={isVideo ? "Real" : "Authentic"}
                manipulatedLabel={isVideo ? "Fake" : "Tampered"}
              />
              <p className="mt-4 text-sm text-ink-2">
                {isVideo
                  ? "Aggregated over the face scores (one face per sampled frame): if more than 11 faces (and over 40% of them) score above 80% fake, only those are averaged; if over 90% score below 20%, only those are averaged; otherwise all faces are averaged."
                  : "The image is re-compressed and the per-pixel error is fed to a CNN. Edited regions typically recompress differently from the rest of the image."}
              </p>
              {metaWarning && a.verdict === "authentic" && (
                <p className="mt-3 text-sm text-ink-2">
                  The pixel-level model found no manipulation even though editing software touched the file — common for
                  simple crops, resizes or colour corrections.
                </p>
              )}
            </Section>
          )}

          {isVideo && noFaceDetected(a) && (
            <Callout tone="warning" title="No faces found">
              ForgeGuard's video model classifies faces only. Try a clip where a face is clearly visible and well lit for
              most of its length.
            </Callout>
          )}

          {isVideo && a.video && a.video.framePredictions.length > 0 && (
            <Section icon={<FileVideo className="size-4" />} title={`Per-face analysis · ${a.video.framePredictions.length} face crops`}>
              <FrameChart values={a.video.framePredictions} />
              <p className="mt-4 text-xs text-ink-3">
                {a.video.framesSampled} frames sampled evenly across the video; faces detected with MTCNN and resized to
                380×380 before classification.
              </p>
            </Section>
          )}
        </div>
      </div>

      <Card className="p-5 sm:p-6 print-avoid-break">
        <h3 className="mb-2 text-sm font-semibold text-ink">How to read this report</h3>
        <p className="text-sm text-ink-2">
          ForgeGuard's verdicts are model predictions, not proof. Model scores are uncalibrated: they are not the
          probability that a verdict is correct. The image model has not passed an evaluation yet, so image results
          show an experimental score and no verdict. Heavily compressed, very small, or screenshotted media lowers
          reliability. Use this report alongside source verification and expert review before acting on it.
        </p>
      </Card>
    </article>
  );
}
