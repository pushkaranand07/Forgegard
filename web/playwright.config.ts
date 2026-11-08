import { defineConfig, devices } from "@playwright/test";

// Browser checks for the UI: accessibility (axe), layout at phone width, page structure.
// The API is stubbed per test, so no backend is needed.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: { baseURL: "http://127.0.0.1:4317", ...devices["Desktop Chrome"] },
  webServer: {
    command: "npx vite --port 4317 --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:4317",
    reuseExistingServer: false, // never test some other app that happens to hold the port
    timeout: 60_000,
  },
});
