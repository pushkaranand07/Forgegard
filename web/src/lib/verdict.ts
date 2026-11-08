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
          ? `The classifier scored the faces in this video as genuine (model score ${formatConfidence(a.confidencePct)}, uncalibrated: not a probability of being right).`
          : `Error-level analysis found no manipulation pattern (model score ${formatConfidence(a.confidencePct)}, uncalibrated: not a probability of being right).`,
      };
    case "manipulated":
      return {
        title: isVideo ? "Likely deepfake" : "Likely tampered",
        short: isVideo ? "Deepfake" : "Tampered",
        tone: "critical",
        icon: ShieldAlert,
        summary: isVideo
          ? `The classifier flagged likely facial manipulation (model score ${formatConfidence(a.confidencePct)}, uncalibrated: not a probability of being right).`
          : `Error-level analysis shows compression inconsistencies typical of edited regions (model score ${formatConfidence(a.confidencePct)}, uncalibrated).`,
      };
    case "inconclusive":
      if (a.label === "UNSUPPORTED") {
        return {
          title: "No verdict for this file type",
          short: "Not applicable",
          tone: "warning",
          icon: CircleHelp,
          summary: a.note ?? "Error level analysis needs a JPEG source, so no score is given.",
        };
      }
      if (a.label === "UNVALIDATED") {
        const score = a.experimentalScore;
        return {
          title: "No verdict: experimental model",
          short: "No verdict",
          tone: "warning",
          icon: CircleHelp,
          summary:
            "The image model has not passed an evaluation yet, so ForgeGuard gives no tampering verdict." +
            (score != null ? ` Experimental score: ${score.toFixed(2)} (uncalibrated, not validated).` : ""),
        };
      }
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
