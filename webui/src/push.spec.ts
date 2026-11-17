import { afterEach, describe, expect, it, vi } from "vitest";

import {
  currentSubscription,
  decodeKey,
  pushSupported,
  subscribe,
  unsubscribe,
} from "./push";

function subscription(): PushSubscription {
  return {
    endpoint: "https://push.example/1",
    unsubscribe: vi.fn().mockResolvedValue(true),
  } as unknown as PushSubscription;
}

function stubBrowser() {
  const registration = {
    pushManager: {
      getSubscription: vi.fn().mockResolvedValue(null),
      subscribe: vi.fn().mockResolvedValue(subscription()),
    },
  };
  vi.stubGlobal("PushManager", class {});
  vi.stubGlobal("Notification", {
    permission: "granted",
    requestPermission: vi.fn().mockResolvedValue("granted"),
  });
  vi.stubGlobal("navigator", {
    serviceWorker: { ready: Promise.resolve(registration) },
  });
  return registration;
}

afterEach(() => vi.unstubAllGlobals());

describe("push", () => {
  it("decodes an unpadded base64url VAPID key", () => {
    expect([...decodeKey("AQAB")]).toEqual([1, 0, 1]);
  });

  it("decodes url-safe characters and padding", () => {
    expect([...decodeKey("-_8")]).toEqual([0xfb, 0xff]);
  });

  it("detects missing browser support", () => {
    vi.stubGlobal("navigator", {});

    expect(pushSupported()).toBe(false);
  });

  it("returns the existing browser subscription", async () => {
    const registration = stubBrowser();
    const existing = subscription();
    registration.pushManager.getSubscription.mockResolvedValue(existing);

    await expect(currentSubscription()).resolves.toBe(existing);
  });

  it("subscribes with the decoded application server key", async () => {
    const registration = stubBrowser();

    await subscribe("AQAB");

    expect(registration.pushManager.subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: new Uint8Array([1, 0, 1]),
    });
  });

  it("unsubscribes and returns the endpoint", async () => {
    const registration = stubBrowser();
    const existing = subscription();
    registration.pushManager.getSubscription.mockResolvedValue(existing);

    await expect(unsubscribe()).resolves.toBe("https://push.example/1");
    expect(existing.unsubscribe).toHaveBeenCalled();
  });
});
