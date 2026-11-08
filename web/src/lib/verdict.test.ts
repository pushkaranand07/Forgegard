import { describe, expect, it } from "vitest";
import type { Analysis } from "./types";
import { verdictMeta } from "./verdict";

const base: Analysis = {
  id: "1",
  createdAt: new Date().toISOString(),
  source: "single",
  fileName: "f",
  fileSize: 1,
  mediaType: "video",
  verdict: "manipulated",
  label: "FAKE",
  confidencePct: 97,
  device: "cpu",
  processingMs: 1,
  probs: { authentic: 0.03, manipulated: 0.97 },
  video: { framesSampled: 32, framePredictions: Array(20).fill(0.97), notes: [] },
};
const a = (over: Partial<Analysis>): Analysis => ({ ...base, ...over });

describe("verdict wording never overclaims (audit I16)", () => {
  const cases: Partial<Analysis>[] = [
    {},
    { verdict: "authentic", label: "REAL" },
    { mediaType: "image", verdict: "authentic", label: "AUTHENTIC" },
    { mediaType: "image", verdict: "manipulated", label: "TAMPERED" },
  ];
  it.each(cases)("says 'model score', never 'confident' (%o)", (over) => {
    const m = verdictMeta(a(over));
    expect(m.summary).toMatch(/model score/);
    expect(m.summary).not.toMatch(/confiden/i);
  });
});

describe("inconclusive results explain why", () => {
  it("unvalidated image model: no verdict, experimental score", () => {
    const m = verdictMeta(a({ mediaType: "image", verdict: "inconclusive", label: "UNVALIDATED", experimentalScore: 0.87 }));
    expect(m.title).toBe("No verdict: experimental model");
    expect(m.summary).toContain("0.87");
    expect(m.summary).toMatch(/not validated/);
  });

  it("unsupported format uses the server's reason", () => {
    const m = verdictMeta(a({ mediaType: "image", verdict: "inconclusive", label: "UNSUPPORTED", note: "needs JPEG" }));
    expect(m.short).toBe("Not applicable");
    expect(m.summary).toBe("needs JPEG");
  });

  it.each([
    ["NO_FACE_DETECTED", /No face was found in any of the 32/],
    ["NO_CONSENSUS", /disagree/],
    ["TOO_FEW_FACES", /Only 20 faces/],
  ])("%s", (note, pattern) => {
    const m = verdictMeta(a({ verdict: "inconclusive", label: "UNSURE", video: { ...base.video!, notes: [note] } }));
    expect(m.title).toBe("Inconclusive");
    expect(m.summary).toMatch(pattern);
  });

  it("errors show the error message", () => {
    expect(verdictMeta(a({ verdict: "error", error: "boom" })).summary).toBe("boom");
  });
});
