import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const app = {
    mount: vi.fn(),
    config: {} as {
      errorHandler?: (error: unknown, instance: unknown, info: string) => void;
    },
  };
  return { app };
});

vi.mock("vue", () => ({ createApp: vi.fn(() => mocks.app) }));
vi.mock("@sentry/vue", () => ({
  init: vi.fn(),
  captureException: vi.fn(),
}));
vi.mock("./App.vue", () => ({ default: { name: "AppStub" } }));
vi.mock("./theme", () => ({}));

import * as Sentry from "@sentry/vue";

describe("main", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mocks.app.config = {};
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("initializes Sentry with the DSN and mounts the app", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "https://dsn.example/1");

    await import("./main");

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        app: mocks.app,
        dsn: "https://dsn.example/1",
        release: expect.stringMatching(/^mobileui-web@\d+\.\d+\.\d+$/),
        environment: "development",
        tracesSampleRate: 0,
      }),
    );
    expect(mocks.app.mount).toHaveBeenCalledWith("#app");
  });

  it("skips Sentry init without a DSN", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");

    await import("./main");

    expect(Sentry.init).not.toHaveBeenCalled();
    expect(mocks.app.mount).toHaveBeenCalledWith("#app");
  });

  it("reports errors to Sentry and the console", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    await import("./main");

    const error = new Error("boom");
    mocks.app.config.errorHandler?.(error, null, "render");

    expect(Sentry.captureException).toHaveBeenCalledWith(error, {
      extra: { info: "render" },
    });
    expect(consoleError).toHaveBeenCalledWith(error);
  });

  it("registers the service worker on load", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    const register = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { register },
    });

    await import("./main");
    window.dispatchEvent(new Event("load"));

    expect(register).toHaveBeenCalledWith("/sw.js");
  });
});
