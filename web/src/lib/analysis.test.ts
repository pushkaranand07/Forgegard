import { describe, expect, it } from "vitest";
import {
  DEFAULT_LIMITS,
  errorAnalysis,
  extensionOf,
  fromImageResponse,
  fromUnifiedResult,
  fromVideoResponse,
  mediaTypeFor,
  newId,
  noFaceDetected,
  validateFile,
} from "./analysis";
import type { ImageApiResponse, UnifiedApiResult, VideoApiResponse } from "./types";

const meta = { fileName: "a.jpg", fileSize: 1234 };
const file = (name: string, size: number) => ({ name, size }) as File;

const image = (over: Partial<ImageApiResponse> = {}): ImageApiResponse => ({
  label: "UNVALIDATED",
  predicted_class: -1,
  authentic_prob: 0.13,
  tampered_prob: 0.87,
  confidence_pct: null,
  experimental: true,
  reason: "not validated",
  device: "cpu",
  level1: { software_found: false, software_signature: "", notes: [] },
  original_image: null,
  processing_time_ms: 10,
  model: { model_name: "m", weights_sha256: "abc", pipeline_version: "1" },
  ...over,
});

const video = (over: Partial<VideoApiResponse> = {}): VideoApiResponse =>
  ({
    label: "FAKE",
    predicted_class: 0,
    fake_prob: 0.97,
    real_prob: 0.03,
    confidence_pct: 97,
    device: "cpu",
    num_frames_processed: 20,
    num_frames_sampled: 32,
    num_faces_analyzed: 20,
    frame_predictions: Array(20).fill(0.97),
    processing_time_ms: 2000,
    notes: [],
    status: "success",
    model: { model_name: "m", weights_sha256: "abc", pipeline_version: "1" },
    ...over,
  }) as VideoApiResponse;

describe("file rules", () => {
  it("reads extensions case-insensitively", () => {
    expect(extensionOf("Photo.JPG")).toBe("jpg");
    expect(extensionOf("noext")).toBe("");
  });

  it("routes by extension", () => {
    expect(mediaTypeFor("a.webp")).toBe("image");
    expect(mediaTypeFor("a.gif")).toBe("video");
    expect(mediaTypeFor("a.bmp")).toBeNull(); // dropped in phase 1
    expect(mediaTypeFor("a.txt")).toBeNull();
  });

  it("validates type, emptiness and size", () => {
    expect(validateFile(file("a.txt", 10))).toMatch(/not supported/);
    expect(validateFile(file("a.jpg", 0))).toBe("This file is empty.");
    expect(validateFile(file("a.jpg", (DEFAULT_LIMITS.max_upload_mb + 1) * 1024 * 1024))).toMatch(/larger/);
    expect(validateFile(file("a.jpg", 10))).toBeNull();
  });

  it("makes unique ids", () => {
    expect(newId()).not.toBe(newId());
  });
});

describe("image responses", () => {
  it("UNVALIDATED keeps an experimental score but no verdict or probability bar", () => {
    const a = fromImageResponse(image(), meta);
    expect(a.verdict).toBe("inconclusive");
    expect(a.probs).toBeNull();
    expect(a.experimentalScore).toBe(0.87);
    expect(a.note).toBe("not validated");
  });

  it("UNSUPPORTED has no score", () => {
    const a = fromImageResponse(
      image({ label: "UNSUPPORTED", authentic_prob: null, tampered_prob: null, reason: "needs JPEG" }),
      meta,
    );
    expect(a.verdict).toBe("inconclusive");
    expect(a.experimentalScore).toBeNull();
    expect(a.note).toBe("needs JPEG");
  });

  it("a validated verdict gets probabilities", () => {
    const a = fromImageResponse(
      image({ label: "TAMPERED", predicted_class: 0, confidence_pct: 87, experimental: false }),
      meta,
    );
    expect(a.verdict).toBe("manipulated");
    expect(a.probs).toEqual({ authentic: 0.13, manipulated: 0.87 });
  });
});

describe("video responses", () => {
  it("maps a decided verdict with probabilities", () => {
    const a = fromVideoResponse(video(), meta);
    expect(a.verdict).toBe("manipulated");
    expect(a.probs).toEqual({ authentic: 0.03, manipulated: 0.97 });
    expect(a.video?.framesSampled).toBe(32); // the explicit field, not the deprecated one
  });

  it("falls back to the deprecated count for old responses", () => {
    const a = fromVideoResponse(video({ num_frames_sampled: undefined }), meta);
    expect(a.video?.framesSampled).toBe(20);
  });

  it("UNSURE has no probabilities even when a score is reported", () => {
    const a = fromVideoResponse(
      video({ label: "UNSURE", predicted_class: -1, confidence_pct: null, notes: ["NO_CONSENSUS"] }),
      meta,
    );
    expect(a.verdict).toBe("inconclusive");
    expect(a.probs).toBeNull();
  });

  it("detects the no-face case", () => {
    const a = fromVideoResponse(video({ label: "UNSURE", predicted_class: -1, notes: ["NO_FACE_DETECTED"] }), meta);
    expect(noFaceDetected(a)).toBe(true);
    expect(noFaceDetected(fromVideoResponse(video(), meta))).toBe(false);
  });
});

describe("unified results (batch)", () => {
  it("maps an image result through level2", () => {
    const r: UnifiedApiResult = {
      media_type: "image",
      label: "UNVALIDATED",
      confidence_pct: null,
      device: "cpu",
      processing_time_ms: 5,
      level1: { software_found: true, software_signature: "GIMP", notes: [] },
      level2: { authentic_prob: 0.4, tampered_prob: 0.6, method: "ELA + CNN", experimental: true, reason: "x" },
      model: { model_name: "m", weights_sha256: "abc", pipeline_version: "1" },
      status: "success",
    };
    const a = fromUnifiedResult(r, meta);
    expect(a.mediaType).toBe("image");
    expect(a.experimentalScore).toBe(0.6);
    expect(a.image?.softwareSignature).toBe("GIMP");
  });

  it("recovers video probabilities from confidence", () => {
    const r = {
      media_type: "video",
      label: "REAL",
      confidence_pct: 90,
      device: "cpu",
      processing_time_ms: 5,
      frame_predictions: [0.1],
      num_frames_sampled: 32,
    } as UnifiedApiResult;
    const a = fromUnifiedResult(r, meta);
    expect(a.probs?.authentic).toBeCloseTo(0.9);
    expect(a.video?.framesSampled).toBe(32);
  });

  it("builds error entries", () => {
    const a = errorAnalysis({ ...meta, mediaType: "video" }, "boom");
    expect(a.verdict).toBe("error");
    expect(a.error).toBe("boom");
  });
});
