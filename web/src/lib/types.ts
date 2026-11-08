// Response shapes of the Django API, generated from api/openapi.yaml into
// api-schema.ts (`npm run gen:api`; CI fails if it is stale). Never edit those by
// hand: change the spec, which tests/test_openapi_contract.py checks against
// the real responses.
import type { components } from "./api-schema";

type Schemas = components["schemas"];

export type Level1Metadata = Schemas["Level1Metadata"];
/** Version block on every detection response */
export type ModelInfo = Schemas["ModelInfo"];
/** POST /api/detect-image/ */
export type ImageApiResponse = Schemas["ImageResult"];
/** POST /api/detect-video/ */
export type VideoApiResponse = Schemas["VideoResult"];
/** POST /api/detect/, and each entry of a batch */
export type UnifiedApiResult = Schemas["UnifiedResult"];
/** POST /api/detect/batch, GET /api/batches/<id>/ */
export type BatchApiResponse = Schemas["BatchStatus"];
/** GET /api/health/ */
export type HealthResponse = Schemas["Health"];
export type ErrorCode = Schemas["ErrorCode"];

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
  /** null when the model produced no score */
  confidencePct: number | null;
  device: string;
  processingMs: number;
  /** Probability (0–1) of each class; null when the model did not decide */
  probs: { authentic: number; manipulated: number } | null;
  /** Unvalidated image model: its raw tampering score (0–1), shown as experimental, never as a verdict */
  experimentalScore?: number | null;
  /** Why no verdict was given (unvalidated model, unsupported format) */
  note?: string | null;
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
