import { flushPromises, mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";
import { setLocale, t } from "./i18n";
import type { Session } from "./types";
import { detail, files, labels, torrent } from "./components/__fixtures__";
import App from "./App.vue";

vi.mock("./api", () => {
  class UnauthorizedError extends Error {}
  return {
    UnauthorizedError,
    getToken: vi.fn(),
    setToken: vi.fn(),
    getHealth: vi.fn(),
    getSession: vi.fn(),
    getLabels: vi.fn(),
    listTorrents: vi.fn(),
    eventsUrl: vi.fn(),
    updateTorrent: vi.fn(),
    pauseTorrent: vi.fn(),
    resumeTorrent: vi.fn(),
    queueTorrent: vi.fn(),
    setLabel: vi.fn(),
    removeTorrent: vi.fn(),
    getTorrent: vi.fn(),
    getTorrentFiles: vi.fn(),
    addTorrentMagnet: vi.fn(),
    addTorrentFile: vi.fn(),
  };
});

const session: Session = {
  download_rate: 1024,
  upload_rate: 512,
  payload_download_rate: 1024,
  payload_upload_rate: 512,
  num_torrents: 1,
  paused: false,
  version: "2.2.0",
  download_location: "/data/downloads",
  queue: {},
};

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private listeners: Record<string, (event: MessageEvent) => void> = {};

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void): void {
    this.listeners[type] = listener;
  }

  close(): void {}

  emit(type: string, data: unknown): void {
    this.listeners[type]?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

const RecycleScrollerStub = {
  props: ["items"],
  template: `<div class="scroller"><template v-for="item in items" :key="item.id"><slot :item="item" /></template></div>`,
};

function mountApp() {
  return mount(App, {
    global: {
      stubs: {
        RecycleScroller: RecycleScrollerStub,
        teleport: true,
      },
    },
  });
}

beforeEach(() => {
  setLocale("en");
  vi.clearAllMocks();
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);

  vi.mocked(api.getToken).mockReturnValue("dev-token");
  vi.mocked(api.getHealth).mockResolvedValue({ ok: true, version: "0.1.3", port: 8113 });
  vi.mocked(api.getSession).mockResolvedValue(session);
  vi.mocked(api.getLabels).mockResolvedValue({ labels, no_label: 1 });
  vi.mocked(api.listTorrents).mockResolvedValue({
    total: 1,
    offset: 0,
    limit: 50,
    torrents: [torrent],
  });
  vi.mocked(api.eventsUrl).mockReturnValue("/api/events?token=dev-token");
  vi.mocked(api.getTorrent).mockResolvedValue(detail);
  vi.mocked(api.getTorrentFiles).mockResolvedValue({
    total: files.length,
    offset: 0,
    limit: 100,
    files,
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("loads the session, labels, list and version", async () => {
    const wrapper = mountApp();
    await flushPromises();

    expect(api.getSession).toHaveBeenCalled();
    expect(api.getLabels).toHaveBeenCalled();
    expect(api.listTorrents).toHaveBeenCalledWith(
      { q: "", state: "", label: "", sort: "name" },
      0,
      50,
    );
    expect(wrapper.text()).toContain(torrent.name);
    expect(wrapper.text()).toContain("MobileUi v0.1.3");

    FakeEventSource.instances[0].onopen?.();
    await nextTick();
    expect(wrapper.get(".sse-dot").classes()).toContain("live");
  });

  it("shows the token gate and authenticates", async () => {
    vi.mocked(api.getToken).mockReturnValue("");
    const wrapper = mountApp();
    await flushPromises();

    expect(api.getSession).not.toHaveBeenCalled();
    await wrapper.get('input[type="password"]').setValue("new-token");

    vi.mocked(api.getToken).mockReturnValue("new-token");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(api.setToken).toHaveBeenCalledWith("new-token");
    expect(wrapper.text()).toContain(torrent.name);
  });

  it("returns to the gate on an unauthorized response", async () => {
    vi.mocked(api.getSession).mockRejectedValueOnce(new api.UnauthorizedError());
    const wrapper = mountApp();
    await flushPromises();

    expect(wrapper.text()).toContain(t("token.invalid"));
    expect(wrapper.find('input[type="password"]').exists()).toBe(true);
  });

  it("applies SSE session and torrent deltas", async () => {
    const wrapper = mountApp();
    await flushPromises();
    const source = FakeEventSource.instances[0];

    source.emit("session", {
      type: "session",
      id: null,
      fields: { num_torrents: 5 },
    });
    await nextTick();
    expect(wrapper.text()).toContain("5");

    source.emit("torrent", {
      type: "state",
      id: torrent.id,
      fields: { state: "Paused" },
    });
    expect(api.updateTorrent).toHaveBeenCalledWith(
      expect.objectContaining({ id: torrent.id }),
      { state: "Paused" },
    );
  });

  it("debounces the search before reloading", async () => {
    const wrapper = mountApp();
    await flushPromises();
    vi.useFakeTimers();

    await wrapper.get('input[type="search"]').setValue("abc");
    vi.advanceTimersByTime(300);
    await flushPromises();

    expect(api.listTorrents).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "abc" }),
      0,
      50,
    );
  });

  it("opens the add dialog and the detail", async () => {
    const wrapper = mountApp();
    await flushPromises();

    await wrapper.get(`button[aria-label="${t("header.add")}"]`).trigger("click");
    expect(wrapper.get(`[role="dialog"][aria-label="${t("add.title")}"]`)).toBeTruthy();
    await wrapper.get(`[role="dialog"] button[aria-label="${t("sheet.close")}"]`).trigger("click");

    await wrapper.get(`[role="button"][aria-label="${torrent.name}"]`).trigger("click");
    await flushPromises();
    expect(api.getTorrent).toHaveBeenCalledWith(torrent.id);
    expect(wrapper.get(`[role="dialog"][aria-label="${t("detail.title")}"]`)).toBeTruthy();
  });
});
