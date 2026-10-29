import type {
  Analysis,
  HealthResponse,
  ImageApiResponse,
  MediaType,
  UnifiedApiResult,
  Verdict,
  VideoApiResponse,
} from "./types";

// Mirrors the backend defaults; replaced by /api/health/ limits when available.
export const DEFAULT_LIMITS: HealthResponse["limits"] = {
  max_upload_mb: 100,
  max_batch_files: 20,
  image_extensions: ["bmp", "jpeg", "jpg", "png", "tif", "tiff", "webp"],
  video_extensions: ["3gp", "avi", "flv", "gif", "mkv", "mov", "mp4", "webm", "wmv"],
  video_frames_sampled: 32,
};

export function extensionOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i === -1 ? "" : name.slice(i + 1).toLowerCase();
}

export function mediaTypeFor(name: string, limits = DEFAULT_LIMITS): MediaType | null {
  const ext = extensionOf(name);
  if (limits.image_extensions.includes(ext)) return "image";
  if (limits.video_extensions.includes(ext)) return "video";
  return null;
}

/** Returns an error message, or null when the file can be uploaded. */
export function validateFile(file: File, limits = DEFAULT_LIMITS): string | null {
  if (!mediaTypeFor(file.name, limits)) {
    const ext = extensionOf(file.name);
    return `${ext ? `.${ext}` : "This"} files are not supported. Use an image (${limits.image_extensions.join(", ")}) or a video (${limits.video_extensions.join(", ")}).`;
  }
  if (file.size === 0) return "This file is empty.";
  if (file.size > limits.max_upload_mb * 1024 * 1024) {
    return `This file is larger than the ${limits.max_upload_mb} MB limit.`;
  }
  return null;
}

export function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function verdictFor(label: string): Verdict {
  switch (label) {
    case "AUTHENTIC":
    case "REAL":
      return "authentic";
    case "TAMPERED":
    case "FAKE":
      return "manipulated";
    case "UNSURE":
    case "UNKNOWN":
      return "inconclusive";
    default:
      return "error";
  }
}

interface FileMeta {
  fileName: string;
  fileSize: number;
  thumbnail?: string;
  source?: Analysis["source"];
}

function base(meta: FileMeta): Pick<Analysis, "id" | "createdAt" | "source" | "fileName" | "fileSize" | "thumbnail"> {
  return {
    id: newId(),
    createdAt: new Date().toISOString(),
    source: meta.source ?? "single",
    fileName: meta.fileName,
    fileSize: meta.fileSize,
    thumbnail: meta.thumbnail,
  };
}

export function fromImageResponse(r: ImageApiResponse, meta: FileMeta): Analysis {
  return {
    ...base(meta),
    mediaType: "image",
    verdict: verdictFor(r.label),
    label: r.label,
    confidencePct: r.confidence_pct,
    device: r.device,
    processingMs: r.processing_time_ms,
    probs: { authentic: r.authentic_prob, manipulated: r.tampered_prob },
    image: {
      softwareFound: r.level1.software_found,
      softwareSignature: r.level1.software_signature,
      notes: r.level1.notes,
      method: "ELA + CNN",
    },
  };
}

export function fromVideoResponse(r: VideoApiResponse, meta: FileMeta): Analysis {
  const decided = r.predicted_class === 0 || r.predicted_class === 1;
  return {
    ...base(meta),
    mediaType: "video",
    verdict: verdictFor(r.label),
    label: r.label,
    confidencePct: r.confidence_pct,
    device: r.device,
    processingMs: r.processing_time_ms,
    probs: decided ? { authentic: r.real_prob, manipulated: r.fake_prob } : null,
    video: {
      framesSampled: r.num_frames_processed,
      framePredictions: r.frame_predictions,
      notes: r.notes ?? [],
    },
  };
}

export function fromUnifiedResult(r: UnifiedApiResult, meta: FileMeta): Analysis {
  const mediaType: MediaType = r.media_type === "video" ? "video" : "image";
  const verdict = verdictFor(r.label);
  const common = {
    ...base(meta),
    mediaType,
    verdict,
    label: r.label,
    confidencePct: r.confidence_pct,
    device: r.device,
    processingMs: r.processing_time_ms,
    error: r.error,
  };

  if (mediaType === "image") {
    return {
      ...common,
      probs: r.level2 ? { authentic: r.level2.authentic_prob, manipulated: r.level2.tampered_prob } : null,
      image: r.level1
        ? {
            softwareFound: r.level1.software_found,
            softwareSignature: r.level1.software_signature,
            notes: r.level1.notes,
            method: r.level2?.method ?? "ELA + CNN",
          }
        : undefined,
    };
  }

  const preds = r.frame_predictions ?? [];
  // The unified endpoint omits class probabilities for video; recover them from
  // the confidence and label, which is exactly how the backend derives them.
  const c = r.confidence_pct / 100;
  const probs =
    verdict === "authentic"
      ? { authentic: c, manipulated: 1 - c }
      : verdict === "manipulated"
        ? { authentic: 1 - c, manipulated: c }
        : null;
  return {
    ...common,
    probs,
    video: {
      framesSampled: r.num_frames_processed ?? 0,
      framePredictions: preds,
      notes: r.notes ?? [],
    },
  };
}

export function errorAnalysis(meta: FileMeta & { mediaType: MediaType }, error: string): Analysis {
  return {
    ...base(meta),
    mediaType: meta.mediaType,
    verdict: "error",
    label: "ERROR",
    confidencePct: 0,
    device: "—",
    processingMs: 0,
    probs: null,
    error,
  };
}

/** True when the video pipeline found no face to classify. */
export function noFaceDetected(a: Analysis): boolean {
  return !!a.video?.notes.includes("NO_FACE_DETECTED");
}
