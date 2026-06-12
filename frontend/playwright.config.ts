import { defineConfig, devices } from "@playwright/test";

const BACKEND_PORT = Number(process.env.PLAYWRIGHT_BACKEND_PORT ?? 8000);
const FRONTEND_PORT = 5173;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      // Frontend only (Vite on :5173) — UI tests block /api/* via beforeEach route.
      // For full E2E with backend, set PLAYWRIGHT_FULL_E2E=1 to also start uvicorn.
      command: `npm run dev -- --port ${FRONTEND_PORT}`,
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    ...(process.env.PLAYWRIGHT_FULL_E2E === "1"
      ? [
          {
            // Use `python -m app.run_dev` because app/main.py requires `if __name__ == "__main__"`
            // guard around ui.run(); uvicorn cannot import main:app directly.
            command: `cd ..\\app && set PYTHONPATH=..&& ..\\venv\\Scripts\\python.exe -c "import runpy; runpy.run_path('main.py', run_name='__main__')"`,
            url: `http://localhost:${BACKEND_PORT}/`,
            reuseExistingServer: !process.env.CI,
            timeout: 60_000,
            stdout: "pipe" as const,
            stderr: "pipe" as const,
          },
        ]
      : []),
  ],
});

