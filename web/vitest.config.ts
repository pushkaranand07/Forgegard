import { defineConfig } from "vitest/config";

// Unit tests for the UI's logic (src/lib). Components and browser-only helpers
// (canvas thumbnails, file downloads) are exercised by the browser checks instead.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/lib/**/*.ts"],
      exclude: ["src/lib/**/*.test.ts", "src/lib/types.ts", "src/lib/thumbnail.ts", "src/lib/download.ts"],
      thresholds: { lines: 80, functions: 80, statements: 80, branches: 70 },
      reporter: ["text", "text-summary"],
    },
  },
});
