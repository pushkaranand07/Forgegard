import { AlertTriangle, CircleHelp, ShieldAlert, ShieldCheck, type LucideIcon } from "lucide-react";
import type { Tone } from "../components/ui";
import { noFaceDetected } from "./analysis";
import { formatConfidence } from "./format";
import type { Analysis } from "./types";

export interface VerdictMeta {
  title: string;
  short: string;
  tone: Tone;
  icon: LucideIcon;
  summary: string;
}

export function verdictMeta(a: Analysis): VerdictMeta {
  const isVideo = a.mediaType === "video";

  switch (a.verdict) {
    case "authentic":
      return {
        title: isVideo ? "No deepfake detected" : "No tampering detected",
        short: isVideo ? "Real" : "Authentic",
        tone: "good",
        icon: ShieldCheck,
        summary: isVideo
          ? `The classifier judged the faces in this video to be genuine with ${formatConfidence(a.confidencePct)} confidence.`
          : `Error-level analysis found no manipulation pattern; the model is ${formatConfidence(a.confidencePct)} confident the image is authentic.`,
      };
    case "manipulated":
      return {
        title: isVideo ? "Likely deepfake" : "Likely tampered",
        short: isVideo ? "Deepfake" : "Tampered",
        tone: "critical",
        icon: ShieldAlert,
        summary: isVideo
          ? `The classifier flagged synthetic facial manipulation with ${formatConfidence(a.confidencePct)} confidence.`
          : `Error-level analysis shows compression inconsistencies typical of edited regions (${formatConfidence(a.confidencePct)} confidence).`,
      };
    case "inconclusive":
      return {
        title: "Inconclusive",
        short: "Inconclusive",
        tone: "warning",
        icon: CircleHelp,
        summary: noFaceDetected(a)
          ? `No face was found in any of the ${a.video?.framesSampled ?? 0} sampled frames. The deepfake model only analyses faces, so it cannot judge this video.`
          : "The model could not reach a decision for this file.",
      };
    default:
      return {
        title: "Analysis failed",
        short: "Error",
        tone: "critical",
        icon: AlertTriangle,
        summary: a.error ?? "The server could not analyse this file.",
      };
  }
}
