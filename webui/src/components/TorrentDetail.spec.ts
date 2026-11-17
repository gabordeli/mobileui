import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { formatRate } from "../format";
import { setLocale, t } from "../i18n";
import type { TorrentFile } from "../types";
import { detail, files, labels } from "./__fixtures__";
import TorrentDetail from "./TorrentDetail.vue";

vi.mock("../api", () => ({
  getTorrent: vi.fn(),
  getTorrentFiles: vi.fn(),
  setFilePriorities: vi.fn(),
  setTorrentLimits: vi.fn(),
  pauseTorrent: vi.fn(),
  resumeTorrent: vi.fn(),
  queueTorrent: vi.fn(),
  setLabel: vi.fn(),
  removeTorrent: vi.fn(),
}));

beforeEach(() => {
  setLocale("en");
  vi.clearAllMocks();
  vi.mocked(api.getTorrent).mockResolvedValue(detail);
  vi.mocked(api.getTorrentFiles).mockResolvedValue({
    total: files.length,
    offset: 0,
    limit: 100,
    files,
  });
  vi.mocked(api.pauseTorrent).mockResolvedValue({ state: "Paused" });
  vi.mocked(api.resumeTorrent).mockResolvedValue({ state: "Downloading" });
  vi.mocked(api.queueTorrent).mockResolvedValue({ action: "top" });
  vi.mocked(api.setLabel).mockResolvedValue({ label: "No Label" });
  vi.mocked(api.removeTorrent).mockResolvedValue({ removed: true });
  vi.mocked(api.setFilePriorities).mockResolvedValue({
    id: detail.id,
    priorities: [4, 4],
  });
  vi.mocked(api.setTorrentLimits).mockResolvedValue({
    id: detail.id,
    max_download_speed: -1,
    max_upload_speed: -1,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function factory(overrides: Record<string, unknown> = {}) {
  return mount(TorrentDetail, {
    props: {
      torrentId: detail.id,
      liveFields: {},
      labels,
      noLabelCount: 1,
      canWrite: true,
      ...overrides,
    },
    global: { stubs: { teleport: true } },
  });
}

function button(wrapper: ReturnType<typeof factory>, label: string) {
  const found = wrapper.findAll("button").find((item) => item.text() === label);
  if (!found) throw new Error(`button not found: ${label}`);
  return found;
}

describe("TorrentDetail", () => {
  it("loads the detail and the first files page", async () => {
    const wrapper = factory();
    await flushPromises();

    expect(api.getTorrent).toHaveBeenCalledWith(detail.id);
    expect(api.getTorrentFiles).toHaveBeenCalledWith(detail.id, 0, 100);
    expect(wrapper.text()).toContain(detail.name);
    expect(wrapper.text()).toContain("/data/downloads");
    expect(wrapper.text()).toContain(files[0].path);
    expect(wrapper.text()).toContain("42.5%");
  });

  it("pauses the torrent and emits the update", async () => {
    const wrapper = factory();
    await flushPromises();

    await button(wrapper, t("sheet.pause")).trigger("click");
    await flushPromises();

    expect(api.pauseTorrent).toHaveBeenCalledWith(detail.id);
    expect(wrapper.emitted("updated")?.[0]).toEqual([
      { id: detail.id, fields: { state: "Paused" } },
    ]);
    expect(wrapper.emitted("toast")?.[0]).toEqual([t("toast.paused")]);
  });

  it("resumes a paused torrent", async () => {
    vi.mocked(api.getTorrent).mockResolvedValue({ ...detail, state: "Paused" });
    const wrapper = factory();
    await flushPromises();

    await button(wrapper, t("sheet.resume")).trigger("click");
    await flushPromises();

    expect(api.resumeTorrent).toHaveBeenCalledWith(detail.id);
    expect(wrapper.emitted("updated")?.[0]).toEqual([
      { id: detail.id, fields: { state: "Downloading" } },
    ]);
  });

  it("queues and saves a label", async () => {
    const wrapper = factory();
    await flushPromises();

    await button(wrapper, t("sheet.top")).trigger("click");
    await flushPromises();
    expect(api.queueTorrent).toHaveBeenCalledWith(detail.id, "top");

    await wrapper.get("select").setValue("No Label");
    await button(wrapper, t("sheet.save")).trigger("click");
    await flushPromises();
    expect(api.setLabel).toHaveBeenCalledWith(detail.id, "No Label");
    expect(wrapper.emitted("updated")?.[0]).toEqual([
      { id: detail.id, fields: { label: "No Label" } },
    ]);
  });

  it("removes the torrent with the data flag", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const wrapper = factory();
    await flushPromises();

    await wrapper.get('.detail-remove input[type="checkbox"]').setValue(true);
    await button(wrapper, t("detail.remove")).trigger("click");
    await flushPromises();

    expect(api.removeTorrent).toHaveBeenCalledWith(detail.id, true);
    expect(wrapper.emitted("removed")?.[0]).toEqual([detail.id]);
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("loads more files at the next offset", async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({
      index,
      path: `file-${index}.bin`,
      size: 1024,
      offset: 0,
      progress: 0,
      priority: 4,
    })) satisfies TorrentFile[];
    const secondPage = Array.from({ length: 50 }, (_, index) => ({
      index: 100 + index,
      path: `file-${100 + index}.bin`,
      size: 1024,
      offset: 0,
      progress: 0,
      priority: 4,
    })) satisfies TorrentFile[];
    vi.mocked(api.getTorrentFiles)
      .mockResolvedValueOnce({ total: 250, offset: 0, limit: 100, files: firstPage })
      .mockResolvedValueOnce({ total: 250, offset: 100, limit: 100, files: secondPage });

    const wrapper = factory();
    await flushPromises();

    await button(wrapper, t("detail.moreFiles")).trigger("click");
    await flushPromises();

    expect(api.getTorrentFiles).toHaveBeenCalledTimes(2);
    expect(api.getTorrentFiles).toHaveBeenLastCalledWith(detail.id, 100, 100);
    expect(wrapper.text()).toContain("file-149.bin");
  });

  it("shows the load error and retries", async () => {
    vi.mocked(api.getTorrent).mockRejectedValueOnce(new Error("boom"));
    const wrapper = factory();
    await flushPromises();

    expect(wrapper.text()).toContain("boom");
    await wrapper.get(".detail-state button").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain(detail.name);
  });

  it("toggles a file priority and marks it skipped", async () => {
    vi.mocked(api.setFilePriorities).mockResolvedValue({
      id: detail.id,
      priorities: [0, 4],
    });
    const wrapper = factory();
    await flushPromises();

    await wrapper.findAll(".file-check")[0].setValue(false);
    await flushPromises();

    expect(api.setFilePriorities).toHaveBeenCalledWith(detail.id, {
      files: [{ index: 0, priority: 0 }],
    });
    expect(wrapper.findAll(".file-row")[0].classes()).toContain("skipped");
    expect(wrapper.emitted("toast")?.[0]).toEqual([t("toast.files")]);
  });

  it("keeps only one file with the only action", async () => {
    vi.mocked(api.setFilePriorities).mockResolvedValue({
      id: detail.id,
      priorities: [0, 4],
    });
    const wrapper = factory();
    await flushPromises();

    await button(wrapper, t("files.only")).trigger("click");
    await flushPromises();

    expect(api.setFilePriorities).toHaveBeenCalledWith(detail.id, { only: 0 });
    expect(wrapper.findAll(".file-row")[0].classes()).toContain("skipped");
    expect(wrapper.findAll(".file-row")[1].classes()).not.toContain("skipped");
  });

  it("filters the loaded files by path", async () => {
    const wrapper = factory();
    await flushPromises();

    await wrapper.get(".files-search").setValue("srt");

    expect(wrapper.findAll(".file-row")).toHaveLength(1);
    expect(wrapper.text()).toContain("demo-movie.srt");
    expect(wrapper.text()).not.toContain("demo-movie.mkv");
  });

  it("saves the per-torrent speed limits", async () => {
    vi.mocked(api.setTorrentLimits).mockResolvedValue({
      id: detail.id,
      max_download_speed: 256,
      max_upload_speed: 64,
    });
    const wrapper = factory();
    await flushPromises();

    await wrapper
      .get(`input[aria-label="${t("limits.download")}"]`)
      .setValue(256);
    await wrapper
      .get(`input[aria-label="${t("limits.upload")}"]`)
      .setValue(64);
    await wrapper.get(".limits-inline .action").trigger("click");
    await flushPromises();

    expect(api.setTorrentLimits).toHaveBeenCalledWith(detail.id, {
      max_download_speed: 256,
      max_upload_speed: 64,
    });
    expect(wrapper.emitted("toast")?.[0]).toEqual([t("toast.limits")]);
  });

  it("applies live fields to the detail", async () => {
    const wrapper = factory();
    await flushPromises();

    await wrapper.setProps({ liveFields: { download_payload_rate: 123456 } });
    await flushPromises();

    expect(wrapper.text()).toContain(formatRate(123456));
  });

  it("hides the write actions for a read-only account", async () => {
    const wrapper = factory({ canWrite: false });
    await flushPromises();

    expect(wrapper.find(".detail-actions").exists()).toBe(false);
    expect(wrapper.find(".detail-remove").exists()).toBe(false);
    expect(wrapper.find("select").exists()).toBe(false);
    expect(wrapper.find(".file-check").exists()).toBe(false);
    expect(wrapper.get(".readonly-note").text()).toBe(t("auth.readonly"));
    expect(wrapper.text()).toContain(files[0].path);
  });
});
