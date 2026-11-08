import { describe, expect, it } from "vitest";
import { handOffFile, takeHandedOffFile } from "./handoff";
import {
  formatBytes,
  formatConfidence,
  formatDuration,
  formatPct,
  formatProb,
  formatRelative,
  shortId,
} from "./format";

describe("format", () => {
  it("bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(150 * 1024 * 1024)).toBe("150 MB");
  });

  it("durations", () => {
    expect(formatDuration(0)).toBe("—");
    expect(formatDuration(250)).toBe("250 ms");
    expect(formatDuration(12_340)).toBe("12.3 s");
    expect(formatDuration(125_000)).toBe("2m 5s");
  });

  it("never rounds a score up to certainty", () => {
    expect(formatConfidence(null)).toBe("—");
    expect(formatConfidence(99.96)).toBe(">99.9%");
    expect(formatConfidence(53.4)).toBe("53.4%");
    expect(formatProb(0.99999)).toBe(">99.9%");
    expect(formatProb(0.00001)).toBe("<0.1%");
    expect(formatProb(0.25)).toBe("25.0%");
    expect(formatPct(0.5, 0)).toBe("50%");
  });

  it("relative times", () => {
    const ago = (ms: number) => new Date(Date.now() - ms).toISOString();
    expect(formatRelative(ago(10_000))).toBe("just now");
    expect(formatRelative(ago(5 * 60_000))).toBe("5 min ago");
    expect(formatRelative(ago(3 * 3_600_000))).toBe("3 h ago");
    expect(formatRelative(ago(2 * 86_400_000))).toBe("2 d ago");
  });

  it("short ids", () => {
    expect(shortId("ab12-cd34-ef56")).toBe("AB12CD34");
  });
});

describe("file handoff between pages", () => {
  it("hands a file over once, and only briefly", () => {
    const f = { name: "a.jpg" } as File;
    handOffFile(f);
    expect(takeHandedOffFile()?.file).toBe(f);
    expect(takeHandedOffFile()).toBeNull();
    handOffFile(f, Date.now() - 10_000); // expired
    expect(takeHandedOffFile()).toBeNull();
  });
});
