// Response shapes of the Django API (see api/*.py). Kept 1:1 with the backend.

export interface Level1Metadata {
  software_found: boolean;
  software_signature: string;
  notes: string[];
}

/** POST /api/detect-image/ */
export interface ImageApiResponse {
  label: "AUTHENTIC" | "TAMPERED";
  predicted_class: 0 | 1;
  authentic_prob: number;
  tampered_prob: number;
  confidence_pct: number;
  device: string;
  level1: Level1Metadata;
  /** Saved filename, or null unless the server keeps uploads (FORGEGUARD_KEEP_UPLOADS) */
  original_image: string | null;
  processing_time_ms: number;
}

/** POST /api/detect-video/ */
export interface VideoApiResponse {
  label: "REAL" | "FAKE" | "UNSURE" | "UNKNOWN" | "ERROR";
  predicted_class: number;
  fake_prob: number;
  real_prob: number;
  confidence_pct: number;
  device: string;
  num_frames_processed: number;
  frame_predictions: number[];
  processing_time_ms: number;
  notes: string[];
  status: string;
}

/** One entry of POST /api/detect/batch (also the shape of POST /api/detect/) */
export interface UnifiedApiResult {
  media_type: "image" | "video" | "unknown";
  label: string;
  confidence_pct: number;
  device: string;
  processing_time_ms: number;
  level1?: Level1Metadata;
  level2?: { authentic_prob: number; tampered_prob: number; method: string };
  num_frames_processed?: number;
  frame_predictions?: number[];
  notes?: string[];
  error?: string;
  file_index?: number;
  file_name?: string;
}

export interface BatchApiResponse {
  status: "success" | "partial_error" | "error";
  results: UnifiedApiResult[];
  errors: { file_index: number; file_name: string; error: string }[];
  num_success: number;
  num_errors: number;
  processing_time_ms: number;
}

/** GET /api/health/ */
export interface HealthResponse {
  status: "ok" | "degraded";
  device: "cpu" | "cuda";
  gpu_name: string | null;
  models: Record<"image" | "video", { name: string; file: string; present: boolean; loaded: boolean; size_mb: number }>;
  limits: {
    max_upload_mb: number;
    max_batch_files: number;
    image_extensions: string[];
    video_extensions: string[];
    video_frames_sampled: number;
  };
}

// ── Normalized model used throughout the UI ──────────────────────────────────

export type MediaType = "image" | "video";
export type Verdict = "authentic" | "manipulated" | "inconclusive" | "error";

export interface Analysis {
  id: string;
  createdAt: string;
  source: "single" | "batch";
  fileName: string;
  fileSize: number;
  mediaType: MediaType;
  /** Small JPEG data URL for history and reports; absent when unavailable */
  thumbnail?: string;
  verdict: Verdict;
  /** Raw backend label, e.g. TAMPERED / FAKE / UNSURE */
  label: string;
  confidencePct: number;
  device: string;
  processingMs: number;
  /** Probability (0–1) of each class; null when the model did not decide */
  probs: { authentic: number; manipulated: number } | null;
  image?: {
    softwareFound: boolean;
    softwareSignature: string;
    notes: string[];
    method: string;
  };
  video?: {
    framesSampled: number;
    /** Per-face fake probability, 0–1 */
    framePredictions: number[];
    notes: string[];
  };
  error?: string;
}
