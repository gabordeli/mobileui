import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";

import { formatBytes } from "../format";
import { setLocale, t } from "../i18n";
import type { Session } from "../types";
import SessionSheet from "./SessionSheet.vue";

beforeEach(() => setLocale("en"));

const session: Session = {
  download_rate: 0,
  upload_rate: 0,
  payload_download_rate: 1024,
  payload_upload_rate: 2048,
  num_torrents: 4,
  paused: false,
  free_space: 1024 ** 3,
  version: "2.2.0",
  download_location: "/data/downloads",
  queue: {},
};

function factory(overrides: Record<string, unknown> = {}) {
  return mount(SessionSheet, {
    props: {
      session,
      canWrite: true,
      ...overrides,
    },
    global: { stubs: { teleport: true } },
  });
}

describe("SessionSheet", () => {
  it("shows the free space, torrent count and rates", () => {
    const wrapper = factory();

    expect(wrapper.text()).toContain(formatBytes(1024 ** 3));
    expect(wrapper.text()).toContain("4");
    expect(wrapper.text()).toContain("1.00 KiB/s");
    expect(wrapper.text()).toContain(t("session.pause"));
  });

  it("shows a dash when the free space is unknown", () => {
    const wrapper = factory({ session: { ...session, free_space: null } });

    expect(wrapper.text()).toContain("—");
  });

  it("offers resume when the session is paused", () => {
    const wrapper = factory({ session: { ...session, paused: true } });

    expect(wrapper.text()).toContain(t("session.paused"));
    expect(wrapper.text()).toContain(t("session.resume"));
  });

  it("emits toggle and close", async () => {
    const wrapper = factory();

    await wrapper.get("button.action").trigger("click");
    expect(wrapper.emitted("toggle")).toHaveLength(1);

    await wrapper
      .get(`button[aria-label="${t("sheet.close")}"]`)
      .trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("hides the toggle for a read-only account", () => {
    const wrapper = factory({ canWrite: false });

    expect(wrapper.find("button.action").exists()).toBe(false);
    expect(wrapper.get(".readonly-note").text()).toBe(t("auth.readonly"));
  });
});
