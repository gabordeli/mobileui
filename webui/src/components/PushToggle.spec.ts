import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { setLocale, t } from "../i18n";
import * as push from "../push";
import PushToggle from "./PushToggle.vue";

vi.mock("../api", () => ({
  getPushConfig: vi.fn(),
  subscribePush: vi.fn(),
  unsubscribePush: vi.fn(),
  testPush: vi.fn(),
  getPushSubscriptions: vi.fn(),
  removePushSubscription: vi.fn(),
}));

vi.mock("../push", () => ({
  pushSupported: vi.fn(),
  notificationPermission: vi.fn(),
  requestPermission: vi.fn(),
  currentSubscription: vi.fn(),
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
}));

function subscription(): PushSubscription {
  return {
    endpoint: "https://push.example/1",
    toJSON: () => ({
      endpoint: "https://push.example/1",
      keys: { p256dh: "key", auth: "auth" },
    }),
  } as unknown as PushSubscription;
}

function mountToggle() {
  return mount(PushToggle);
}

beforeEach(() => {
  setLocale("en");
  vi.clearAllMocks();
  vi.mocked(push.pushSupported).mockReturnValue(true);
  vi.mocked(push.notificationPermission).mockReturnValue("default");
  vi.mocked(push.currentSubscription).mockResolvedValue(null);
  vi.mocked(push.requestPermission).mockResolvedValue("granted");
  vi.mocked(push.subscribe).mockResolvedValue(subscription());
  vi.mocked(push.unsubscribe).mockResolvedValue("https://push.example/1");
  vi.mocked(api.getPushConfig).mockResolvedValue({
    enabled: true,
    public_key: "AQAB",
    subscriptions: 0,
  });
  vi.mocked(api.subscribePush).mockResolvedValue({ count: 1 });
  vi.mocked(api.unsubscribePush).mockResolvedValue({ unsubscribed: true });
  vi.mocked(api.testPush).mockResolvedValue({ queued: true });
  vi.mocked(api.getPushSubscriptions).mockResolvedValue({ subscriptions: [] });
  vi.mocked(api.removePushSubscription).mockResolvedValue({
    unsubscribed: true,
  });
});

describe("PushToggle", () => {
  it("offers enabling and stores the browser subscription", async () => {
    const wrapper = mountToggle();
    await flushPromises();

    expect(wrapper.text()).toContain(t("push.off"));
    await wrapper.get(".push-toggle .action").trigger("click");
    await flushPromises();

    expect(push.subscribe).toHaveBeenCalledWith("AQAB");
    expect(api.subscribePush).toHaveBeenCalledWith({
      endpoint: "https://push.example/1",
      keys: { p256dh: "key", auth: "auth" },
    });
    expect(wrapper.text()).toContain(t("push.on"));
    expect(wrapper.text()).toContain(t("push.disable"));
  });

  it("disables an active subscription", async () => {
    vi.mocked(push.currentSubscription).mockResolvedValue(subscription());
    const wrapper = mountToggle();
    await flushPromises();

    expect(wrapper.text()).toContain(t("push.on"));
    await wrapper
      .findAll("button")
      .find((item) => item.text() === t("push.disable"))!
      .trigger("click");
    await flushPromises();

    expect(api.unsubscribePush).toHaveBeenCalledWith(
      "https://push.example/1",
    );
    expect(wrapper.text()).toContain(t("push.off"));
  });

  it("sends a test notification to the current subscription", async () => {
    vi.mocked(push.currentSubscription).mockResolvedValue(subscription());
    const wrapper = mountToggle();
    await flushPromises();

    await wrapper
      .findAll("button")
      .find((item) => item.text() === t("push.test"))!
      .trigger("click");
    await flushPromises();

    expect(api.testPush).toHaveBeenCalledWith("https://push.example/1");
    expect(wrapper.text()).toContain(t("push.testSent"));
  });

  it("lists devices and revokes a subscription", async () => {
    vi.mocked(push.currentSubscription).mockResolvedValue(subscription());
    vi.mocked(api.getPushSubscriptions).mockResolvedValue({
      subscriptions: [
        {
          id: "abc",
          host: "push.example",
          added: 1,
          last_seen: 1,
          user_agent: "Mobile Safari",
        },
      ],
    });
    const wrapper = mountToggle();
    await flushPromises();

    expect(wrapper.text()).toContain("push.example");
    await wrapper
      .findAll("button")
      .find((item) => item.text() === t("push.revoke"))!
      .trigger("click");
    await flushPromises();

    expect(api.removePushSubscription).toHaveBeenCalledWith("abc");
    expect(wrapper.text()).toContain(t("push.revoked"));
  });

  it("explains when notifications are blocked", async () => {
    vi.mocked(push.notificationPermission).mockReturnValue("denied");
    const wrapper = mountToggle();
    await flushPromises();

    expect(wrapper.text()).toContain(t("push.denied"));
    expect(wrapper.text()).toContain(t("push.deniedHint"));
    expect(wrapper.find(".push-toggle .action").exists()).toBe(false);
  });

  it("stops when permission is refused", async () => {
    vi.mocked(push.requestPermission).mockResolvedValue("denied");
    const wrapper = mountToggle();
    await flushPromises();

    await wrapper.get(".push-toggle .action").trigger("click");
    await flushPromises();

    expect(push.subscribe).not.toHaveBeenCalled();
    expect(api.subscribePush).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain(t("push.denied"));
  });

  it("reports an unsupported browser", async () => {
    vi.mocked(push.pushSupported).mockReturnValue(false);
    const wrapper = mountToggle();
    await flushPromises();

    expect(wrapper.text()).toContain(t("push.unsupported"));
    expect(wrapper.find(".push-toggle .action").exists()).toBe(false);
    expect(push.currentSubscription).not.toHaveBeenCalled();
  });
});
