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
  max_download_speed: -1,
  max_upload_speed: -1,
  queue: {
    max_active_downloading: 3,
    max_active_seeding: 5,
    max_active_limit: 8,
    queue_new_to_top: false,
  },
};

function factory(overrides: Record<string, unknown> = {}) {
  return mount(SessionSheet, {
    props: {
      session,
      canWrite: true,
      downHistory: [0, 1024],
      upHistory: [0, 512],
      ...overrides,
    },
    global: { stubs: { teleport: true, PushToggle: true } },
  });
}

describe("SessionSheet", () => {
  it("shows the free space, torrent count and rates", () => {
    const wrapper = factory();

    expect(wrapper.text()).toContain(formatBytes(1024 ** 3));
    expect(wrapper.text()).toContain("4");
    expect(wrapper.text()).toContain("1.00 KiB/s");
    expect(wrapper.text()).toContain(t("session.pause"));
    expect(wrapper.find(".sparkline").exists()).toBe(true);
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

    await wrapper.get(".sheet-actions .action").trigger("click");
    expect(wrapper.emitted("toggle")).toHaveLength(1);

    await wrapper
      .get(`button[aria-label="${t("sheet.close")}"]`)
      .trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("emits the custom speed limits", async () => {
    const wrapper = factory();
    const inputs = wrapper.findAll(".limits-row input");

    await inputs[0].setValue(512);
    await inputs[1].setValue(128);
    await wrapper.get(".limits-actions .action").trigger("click");

    expect(wrapper.emitted("limits")?.[0]).toEqual([
      { max_download_speed: 512, max_upload_speed: 128 },
    ]);
  });

  it("applies the night mode and unlimited presets", async () => {
    const wrapper = factory();
    const buttons = wrapper.findAll(".limits-actions .action");

    await buttons[1].trigger("click");
    await buttons[2].trigger("click");

    expect(wrapper.emitted("limits")?.[0]).toEqual([
      { max_download_speed: 512, max_upload_speed: 128 },
    ]);
    expect(wrapper.emitted("limits")?.[1]).toEqual([
      { max_download_speed: -1, max_upload_speed: -1 },
    ]);
  });

  it("emits the queue settings", async () => {
    const wrapper = factory();
    const inputs = wrapper.findAll(".queue-row input");

    await inputs[0].setValue(2);
    await inputs[1].setValue(4);
    await inputs[2].setValue(-1);
    await wrapper.get(".queue-top input").setValue(true);
    await wrapper.findAll(".limits-actions .action").at(-1)!.trigger("click");

    expect(wrapper.emitted("queue")?.[0]).toEqual([
      {
        max_active_downloading: 2,
        max_active_seeding: 4,
        max_active_limit: -1,
        queue_new_to_top: true,
      },
    ]);
  });

  it("hides the toggle for a read-only account", () => {
    const wrapper = factory({ canWrite: false });

    expect(wrapper.find("button.action").exists()).toBe(false);
    expect(wrapper.find(".limits").exists()).toBe(false);
    expect(wrapper.get(".readonly-note").text()).toBe(t("auth.readonly"));
  });
});
