import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Audit I20: axe found serious colour-contrast failures on every route, the 404 page had
// no <h1>, and /docs overflowed by 759 px at 375 px. Every route, in light, dark (toggle)
// and dark (OS preference only, a separate copy of the tokens), at phone and desktop
// widths: no serious/critical axe violations, no horizontal overflow, one <h1>.

type Theme = "light" | "dark" | "os-dark";

const now = new Date().toISOString();
const base = {
  createdAt: now, source: "single", fileSize: 123_456, device: "cpu", processingMs: 4200,
  confidencePct: null, probs: null,
};
const video = { framesSampled: 32, framePredictions: Array(20).fill(0.93), notes: [] as string[] };
const HISTORY = [
  { ...base, id: "fake", fileName: "clip.mp4", mediaType: "video", verdict: "manipulated", label: "FAKE",
    confidencePct: 93, probs: { authentic: 0.07, manipulated: 0.93 }, video },
  { ...base, id: "real", fileName: "real.mp4", mediaType: "video", verdict: "authentic", label: "REAL",
    confidencePct: 95, probs: { authentic: 0.95, manipulated: 0.05 },
    video: { ...video, framePredictions: Array(20).fill(0.05) } },
  { ...base, id: "unsure", fileName: "unsure.mp4", mediaType: "video", verdict: "inconclusive", label: "UNSURE",
    video: { ...video, notes: ["NO_CONSENSUS"] } },
  { ...base, id: "img", fileName: "photo.jpg", mediaType: "image", verdict: "inconclusive", label: "UNVALIDATED",
    experimentalScore: 0.87, note: "The image model is not validated.",
    image: { softwareFound: true, softwareSignature: "GIMP 2.10", notes: [], method: "ELA + CNN" } },
  { ...base, id: "err", fileName: "broken.jpg", mediaType: "image", verdict: "error", label: "ERROR",
    error: "The image file is corrupt or truncated." },
];

const model = (name: string, file: string) => ({
  name, file, present: true, loaded: true, size_mb: 10, weights_sha256: "abc123def456", verified: true,
  load_state: "loaded", load_error: null, healthy: true,
});
const HEALTH = {
  status: "ok", device: "cpu", gpu_name: null, pipeline_version: "1.1.0",
  models: { image: model("IMDModel", "model_c1.pth"), video: model("EfficientNet-B7", "deepfake_detector_b7.pth") },
  limits: { max_upload_mb: 150, max_batch_files: 20, image_extensions: ["jpg", "jpeg", "png", "webp"],
    video_extensions: ["mp4", "avi", "mov", "mkv", "webm", "gif"], video_frames_sampled: 32 },
};

const ROUTES = [
  "/", "/analyze", "/batch", "/history", "/status", "/docs", "/about", "/no-such-page",
  ...HISTORY.map((a) => `/report/${a.id}`),
];

async function prepare(page: Page, theme: Theme) {
  await page.route("**/api/**", (route) =>
    route.request().url().includes("/api/health")
      ? route.fulfill({ json: HEALTH })
      : route.fulfill({ status: 404, json: { error: "stub", code: "NOT_FOUND" } }),
  );
  await page.emulateMedia({ colorScheme: theme === "light" ? "light" : "dark", reducedMotion: "reduce" });
  await page.addInitScript(
    ([history, t]) => {
      localStorage.setItem("fg-history-v1", history);
      if (t !== "os-dark") localStorage.setItem("fg-theme", t);
    },
    [JSON.stringify(HISTORY), theme] as const,
  );
}

for (const theme of ["light", "dark", "os-dark"] as const) {
  for (const width of [375, 1280]) {
    test.describe(`${theme}, ${width}px`, () => {
      test.use({ viewport: { width, height: 900 } });
      for (const path of ROUTES) {
        test(path, async ({ page }) => {
          await prepare(page, theme);
          await page.goto(path);
          await page.waitForLoadState("networkidle");
          if (theme === "os-dark") await expect(page.locator("html")).not.toHaveAttribute("data-theme");
          else await expect(page.locator("html")).toHaveAttribute("data-theme", theme);

          const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
          const serious = results.violations
            .filter((v) => v.impact === "serious" || v.impact === "critical")
            .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 5).join(" | ")}`);
          expect(serious, "serious/critical axe violations").toEqual([]);

          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
          expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);

          await expect(page.locator("h1"), "exactly one <h1>").toHaveCount(1);
        });
      }
    });
  }
}
