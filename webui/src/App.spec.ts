import { flushPromises, mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";
import { setLocale, t } from "./i18n";
import type { Session } from "./types";
import { detail, files, labels, torrent } from "./components/__fixtures__";
import App from "./App.vue";

vi.mock("./api", () => {
  class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  }
  class UnauthorizedError extends ApiError {
    constructor() {
      super("unauthorized", 401);
    }
  }
  class ForbiddenError extends ApiError {
    constructor(message = "forbidden") {
      super(message, 403);
    }
  }
  return {
    ApiError,
    UnauthorizedError,
    ForbiddenError,
    getToken: vi.fn(),
    setToken: vi.fn(),
    getHealth: vi.fn(),
    getAuthInfo: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    getSession: vi.fn(),
    pauseSession: vi.fn(),
    resumeSession: vi.fn(),
    setSessionLimits: vi.fn(),
    getLabels: vi.fn(),
    listTorrents: vi.fn(),
    listTorrentIds: vi.fn(),
    bulkAction: vi.fn(),
    eventsUrl: vi.fn(),
    updateTorrent: vi.fn(),
    pauseTorrent: vi.fn(),
    resumeTorrent: vi.fn(),
    queueTorrent: vi.fn(),
    setLabel: vi.fn(),
    addLabel: vi.fn(),
    removeLabel: vi.fn(),
    reannounceTorrent: vi.fn(),
    removeTorrent: vi.fn(),
    getTorrent: vi.fn(),
    getTorrentFiles: vi.fn(),
    setFilePriorities: vi.fn(),
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
  free_space: 8 * 1024 ** 3,
  version: "2.2.0",
  download_location: "/data/downloads",
  max_download_speed: -1,
  max_upload_speed: -1,
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
  vi.mocked(api.getAuthInfo).mockResolvedValue({
    mode: "token",
    modes: ["token"],
    token_set: true,
    authenticated: true,
    username: "admin",
    level: 10,
    write: true,
  });
  vi.mocked(api.getSession).mockResolvedValue(session);
  vi.mocked(api.pauseSession).mockResolvedValue({ paused: true });
  vi.mocked(api.resumeSession).mockResolvedValue({ paused: false });
  vi.mocked(api.setSessionLimits).mockResolvedValue({
    max_download_speed: -1,
    max_upload_speed: -1,
  });
  vi.mocked(api.addLabel).mockResolvedValue({ id: "new-label" });
  vi.mocked(api.removeLabel).mockResolvedValue({
    id: "film",
    removed: true,
  });
  vi.mocked(api.getLabels).mockResolvedValue({ labels, no_label: 1 });
  vi.mocked(api.listTorrents).mockResolvedValue({
    total: 1,
    offset: 0,
    limit: 50,
    torrents: [torrent],
  });
  vi.mocked(api.listTorrentIds).mockResolvedValue({
    ids: [torrent.id],
    total: 1,
    limit: 1000,
  });
  vi.mocked(api.bulkAction).mockResolvedValue({ ok: 1, failed: [] });
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
  window.history.replaceState({}, "", "/");
});

describe("App", () => {
  it("opens the add sheet with a shared magnet", async () => {
    const shared = "magnet:?xt=urn:btih:deadbeef&dn=Demo";
    window.history.replaceState(
      {},
      "",
      `/?text=${encodeURIComponent(shared)}`,
    );

    const wrapper = mountApp();
    await flushPromises();

    const dialog = wrapper.get(
      `[role="dialog"][aria-label="${t("add.title")}"]`,
    );
    expect((dialog.get("textarea").element as HTMLTextAreaElement).value).toBe(
      shared,
    );
  });

  it("opens the torrent from a push deep link", async () => {
    window.history.replaceState({}, "", `/?torrent=${torrent.id}`);

    const wrapper = mountApp();
    await flushPromises();

    expect(api.getTorrent).toHaveBeenCalledWith(torrent.id);
    expect(window.location.search).toBe("");
    expect(
      wrapper.get(`[role="dialog"][aria-label="${t("detail.title")}"]`),
    ).toBeTruthy();
  });

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

    expect(wrapper.text()).toContain(t("auth.expired"));
    expect(wrapper.find('input[type="password"]').exists()).toBe(true);
  });

  it("signs in with username and password", async () => {
    vi.mocked(api.getToken).mockReturnValue("");
    vi.mocked(api.getAuthInfo).mockResolvedValue({
      mode: "both",
      modes: ["token", "password"],
      token_set: true,
    });
    vi.mocked(api.login).mockImplementation(async () => {
      vi.mocked(api.getToken).mockReturnValue("sess");
      return { token: "sess", username: "admin", level: 10, expires: 1 };
    });
    const wrapper = mountApp();
    await flushPromises();

    const inputs = wrapper.findAll(".gate-card input");
    await inputs[0].setValue("admin");
    await inputs[1].setValue("pw");
    await wrapper.get("form.gate-card").trigger("submit");
    await flushPromises();

    expect(api.login).toHaveBeenCalledWith("admin", "pw");
    expect(api.setToken).toHaveBeenCalledWith("sess");
    expect(wrapper.text()).toContain(torrent.name);
  });

  it("shows a message for invalid credentials and rate limits", async () => {
    vi.mocked(api.getToken).mockReturnValue("");
    vi.mocked(api.getAuthInfo).mockResolvedValue({
      mode: "password",
      modes: ["password"],
      token_set: false,
    });
    vi.mocked(api.login).mockRejectedValueOnce(new api.UnauthorizedError());
    const wrapper = mountApp();
    await flushPromises();

    await wrapper.findAll(".gate-card input")[0].setValue("admin");
    await wrapper.findAll(".gate-card input")[1].setValue("nope");
    await wrapper.get("form.gate-card").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain(t("auth.invalid"));

    vi.mocked(api.login).mockRejectedValueOnce(new api.ApiError("limited", 429));
    await wrapper.get("form.gate-card").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain(t("auth.tooMany"));
  });

  it("signs out from the account panel", async () => {
    const wrapper = mountApp();
    await flushPromises();

    await wrapper.get(`button[aria-label="${t("header.token")}"]`).trigger("click");
    const logout = wrapper
      .findAll("button")
      .find((button) => button.text() === t("auth.logout"));
    await logout!.trigger("click");
    await flushPromises();

    expect(api.logout).toHaveBeenCalled();
    expect(api.setToken).toHaveBeenCalledWith("");
  });

  it("hides the add button for a read-only account", async () => {
    vi.mocked(api.getAuthInfo).mockResolvedValue({
      mode: "password",
      modes: ["password"],
      token_set: false,
      authenticated: true,
      username: "guest",
      level: 1,
      write: false,
    });
    const wrapper = mountApp();
    await flushPromises();

    expect(
      wrapper.find(`button[aria-label="${t("header.add")}"]`).exists(),
    ).toBe(false);
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

  it("opens the session sheet and pauses every torrent", async () => {
    const wrapper = mountApp();
    await flushPromises();

    await wrapper
      .get(`button[aria-label="${t("session.open")}"]`)
      .trigger("click");

    const dialog = wrapper.get(
      `[role="dialog"][aria-label="${t("session.title")}"]`,
    );
    expect(dialog.text()).toContain("8.00 GiB");
    expect(dialog.text()).toContain(t("session.pause"));
    expect(dialog.find(".sparkline").exists()).toBe(true);

    await dialog.get(".sheet-actions .action").trigger("click");
    await flushPromises();

    expect(api.pauseSession).toHaveBeenCalled();
    expect(wrapper.text()).toContain(t("toast.sessionPaused"));
    expect(
      wrapper
        .get(`[role="dialog"][aria-label="${t("session.title")}"]`)
        .text(),
    ).toContain(t("session.resume"));
  });

  async function selectFirstRow(
    wrapper: ReturnType<typeof mountApp>,
  ): Promise<void> {
    vi.useFakeTimers();
    const row = wrapper.get(`[role="button"][aria-label="${torrent.name}"]`);
    await row.trigger("pointerdown", { button: 0, clientX: 10, clientY: 10 });
    vi.advanceTimersByTime(500);
    await nextTick();
    vi.useRealTimers();
  }

  it("starts selection with a long press and runs a bulk pause", async () => {
    const wrapper = mountApp();
    await flushPromises();

    await selectFirstRow(wrapper);

    const bar = wrapper.get(`[role="region"][aria-label="${t("bulk.title")}"]`);
    expect(bar.text()).toContain(t("bulk.selected", { count: 1 }));

    const pauseButton = bar.findAll("button")[2];
    pauseButton.element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await flushPromises();

    expect(api.bulkAction).toHaveBeenCalledWith({
      action: "pause",
      torrent_ids: [torrent.id],
    });
    expect(wrapper.text()).toContain(t("bulk.done", { ok: 1 }));
    expect(wrapper.find(`[role="region"][aria-label="${t("bulk.title")}"]`).exists()).toBe(false);
  });

  it("selects every matching torrent", async () => {
    const wrapper = mountApp();
    await flushPromises();

    await selectFirstRow(wrapper);
    const bar = wrapper.get(`[role="region"][aria-label="${t("bulk.title")}"]`);
    bar.findAll("button")[1].element.dispatchEvent(
      new MouseEvent("click", { bubbles: true }),
    );
    await flushPromises();

    expect(api.listTorrentIds).toHaveBeenCalledWith({
      q: "",
      state: "",
      label: "",
      sort: "name",
    });
    expect(wrapper.text()).toContain(t("bulk.selected", { count: 1 }));
  });

  it("shows a read-only selection bar without actions", async () => {
    vi.mocked(api.getAuthInfo).mockResolvedValue({
      mode: "password",
      modes: ["password"],
      token_set: false,
      authenticated: true,
      username: "guest",
      level: 1,
      write: false,
    });
    const wrapper = mountApp();
    await flushPromises();

    await selectFirstRow(wrapper);

    const bar = wrapper.get(`[role="region"][aria-label="${t("bulk.title")}"]`);
    expect(bar.get(".readonly-note").text()).toBe(t("auth.readonly"));
    expect(
      bar.findAll("button").some((item) => item.text() === t("bulk.pause")),
    ).toBe(false);
  });

  it("applies the global speed limits", async () => {
    const wrapper = mountApp();
    await flushPromises();

    await wrapper
      .get(`button[aria-label="${t("session.open")}"]`)
      .trigger("click");

    const dialog = wrapper.get(
      `[role="dialog"][aria-label="${t("session.title")}"]`,
    );
    const inputs = dialog.findAll(".limits-row input");
    await inputs[0].setValue(512);
    await inputs[1].setValue(128);
    await dialog.get(".limits-actions .action").trigger("click");
    await flushPromises();

    expect(api.setSessionLimits).toHaveBeenCalledWith({
      max_download_speed: 512,
      max_upload_speed: 128,
    });
    expect(wrapper.text()).toContain(t("toast.limits"));
  });

  it("manages labels from the filter bar", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const wrapper = mountApp();
    await flushPromises();

    await wrapper.get(".filter-labels").trigger("click");
    const selector = `[role="dialog"][aria-label="${t("labels.title")}"]`;

    await wrapper.get(`${selector} .label-add input`).setValue("new-label");
    await wrapper.get(`${selector} .label-add .action`).trigger("click");
    await flushPromises();

    expect(api.addLabel).toHaveBeenCalledWith("new-label");
    expect(wrapper.text()).toContain(t("labels.added"));

    await wrapper.get(`${selector} .label-list .action`).trigger("click");
    await flushPromises();

    expect(api.removeLabel).toHaveBeenCalledWith("film");
    expect(wrapper.text()).toContain(t("labels.removed"));
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
