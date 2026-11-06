import { shortId } from "./format";
import type { Analysis } from "./types";

export function downloadBlob(data: BlobPart, type: string, filename: string) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Exports the analysis without the embedded thumbnail. */
export function downloadJson(a: Analysis | Analysis[], filename?: string) {
  const strip = ({ thumbnail: _t, ...rest }: Analysis) => rest;
  const payload = Array.isArray(a) ? a.map(strip) : strip(a);
  const name = filename ?? (Array.isArray(a) ? "forgeguard-results.json" : `forgeguard-report-${shortId(a.id)}.json`);
  downloadBlob(JSON.stringify(payload, null, 2), "application/json", name);
}

export function downloadCsv(rows: Analysis[], filename = "forgeguard-results.csv") {
  const header = ["report_id", "file_name", "media_type", "verdict", "label", "confidence_pct", "authentic_prob", "manipulated_prob", "metadata_software", "faces_analyzed", "device", "processing_ms", "analyzed_at", "error"];
  const esc = (v: unknown) => {
    const s = v === undefined || v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = rows.map((r) =>
    [
      shortId(r.id),
      r.fileName,
      r.mediaType,
      r.verdict,
      r.label,
      r.confidencePct?.toFixed(2) ?? "",
      r.probs?.authentic.toFixed(4),
      r.probs?.manipulated.toFixed(4),
      r.image?.softwareFound ? r.image.softwareSignature : "",
      r.video?.framePredictions.length,
      r.device,
      Math.round(r.processingMs),
      r.createdAt,
      r.error,
    ]
      .map(esc)
      .join(","),
  );
  downloadBlob([header.join(","), ...lines].join("\n"), "text/csv", filename);
}
