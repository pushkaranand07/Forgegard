import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, FileImage, FileVideo } from "lucide-react";
import { formatBytes, formatConfidence, formatRelative } from "../lib/format";
import type { Analysis } from "../lib/types";
import { verdictMeta } from "../lib/verdict";
import { Badge } from "./ui";

export default function HistoryRow({ analysis: a, trailing }: { analysis: Analysis; trailing?: ReactNode }) {
  const v = verdictMeta(a);
  const Icon = v.icon;
  const showConfidence = a.verdict === "authentic" || a.verdict === "manipulated";

  return (
    <div className="flex items-center gap-2 pr-2">
      <Link to={`/report/${a.id}`} className="flex min-w-0 flex-1 items-center gap-4 p-4 hover:bg-surface-2/60">
        <div className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-surface-2 text-ink-3">
          {a.thumbnail ? (
            <img src={a.thumbnail} alt="" className="size-full object-cover" />
          ) : a.mediaType === "video" ? (
            <FileVideo className="size-5" />
          ) : (
            <FileImage className="size-5" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink" title={a.fileName}>
            {a.fileName}
          </p>
          <p className="mt-0.5 text-xs text-ink-3">
            {a.mediaType === "video" ? "Video" : "Image"} · {formatBytes(a.fileSize)} · {formatRelative(a.createdAt)}
            {a.source === "batch" && " · batch"}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-3">
          {showConfidence && <span className="text-sm font-medium text-ink tabular">{formatConfidence(a.confidencePct)}</span>}
          <Badge tone={v.tone}>
            <Icon className="size-3" aria-hidden />
            {v.short}
          </Badge>
        </div>
        <ChevronRight className="size-4 shrink-0 text-ink-3" aria-hidden />
      </Link>
      {trailing}
    </div>
  );
}
