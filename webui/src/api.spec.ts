import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ForbiddenError,
  UnauthorizedError,
  addLabel,
  addTorrentFile,
  addTorrentMagnet,
  eventsUrl,
  getAuthInfo,
  getHealth,
  getLabels,
  getSession,
  getToken,
  getTorrent,
  getTorrentFiles,
  getPushSubscriptions,
  listTorrents,
  login,
  logout,
  moveTorrent,
  pauseTorrent,
  queueTorrent,
  reannounceTorrent,
  removeLabel,
  removePushSubscription,
  removeTorrent,
  resumeTorrent,
  setFilePriorities,
  setLabel,
  setSessionLimits,
  setToken,
  setTorrentLimits,
} from "./api";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request", () => {
  it("sends the bearer token and parses JSON", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ ok: true, version: "0.1.2", port: 8113 }));
    vi.stubGlobal("fetch", fetchMock);
    setToken("secret");

    await expect(getHealth()).resolves.toMatchObject({
      ok: true,
      version: "0.1.2",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/health");
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("authorization")).toBe("Bearer secret");
  });

  it("maps 401 to UnauthorizedError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));

    await expect(getSession()).rejects.toBeInstanceOf(UnauthorizedError);
  });

  it("maps 403 to ForbiddenError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 403 })));

    await expect(getSession()).rejects.toBeInstanceOf(ForbiddenError);
  });

  it("maps API errors with the server message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ message: "boom" }, 500)),
    );

    await expect(getHealth()).rejects.toMatchObject({
      status: 500,
      message: "boom",
    });
  });
});

describe("listTorrents", () => {
  it("builds the query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ total: 0, offset: 50, limit: 50, torrents: [] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listTorrents(
      { q: "a b", state: "Seeding", label: "x", sort: "name" },
      50,
      50,
    );

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/torrents?offset=50&limit=50&sort=name&q=a+b&state=Seeding&label=x",
    );
  });
});

describe("tokens and SSE", () => {
  it("stores and clears the token", () => {
    setToken("x");
    expect(getToken()).toBe("x");
    setToken("");
    expect(getToken()).toBe("");
  });

  it("encodes the token in the SSE URL", () => {
    setToken("a b");
    expect(eventsUrl()).toBe("/api/events?token=a%20b");
  });
});

describe("addTorrentMagnet", () => {
  it("posts JSON options", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ id: "abc" }));
    vi.stubGlobal("fetch", fetchMock);

    await addTorrentMagnet("magnet:?xt=urn:btih:abc", {
      label: "test",
      add_paused: true,
    });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/torrents");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(
      JSON.stringify({
        magnet: "magnet:?xt=urn:btih:abc",
        label: "test",
        add_paused: true,
      }),
    );
  });
});

describe("torrent actions", () => {
  function mockFetch(payload: unknown = {}) {
    const fetchMock = vi.fn((_path: string, _init: RequestInit) =>
      Promise.resolve(jsonResponse(payload)),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("pauses and resumes with encoded ids", async () => {
    const fetchMock = mockFetch({ state: "Paused" });

    await pauseTorrent("a b");
    await resumeTorrent("a/b");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/torrents/a%20b/pause");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/torrents/a%2Fb/resume");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });

  it("removes with the remove_data flag", async () => {
    const fetchMock = mockFetch({ removed: true });

    await removeTorrent("id", true);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/torrents/id/remove");
    expect(fetchMock.mock.calls[0][1].body).toBe(
      JSON.stringify({ remove_data: true }),
    );
  });

  it("queues an action", async () => {
    const fetchMock = mockFetch({ action: "top" });

    await queueTorrent("id", "top");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/torrents/id/queue");
    expect(fetchMock.mock.calls[0][1].body).toBe(
      JSON.stringify({ action: "top" }),
    );
  });

  it("patches the label", async () => {
    const fetchMock = mockFetch({ label: "film" });

    await setLabel("id", "film");

    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(fetchMock.mock.calls[0][1].body).toBe(
      JSON.stringify({ label: "film" }),
    );
  });

  it("uploads a .torrent file with query options", async () => {
    const fetchMock = mockFetch({ id: "abc" });
    const file = new File(["x"], "x.torrent", {
      type: "application/x-bittorrent",
    });

    await addTorrentFile(file, {
      label: "film",
      download_location: "/tmp",
      add_paused: true,
    });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe(
      "/api/torrents?filename=x.torrent&label=film&download_location=%2Ftmp&add_paused=true",
    );
    const headers = init.headers as Headers;
    expect(headers.get("content-type")).toBe("application/x-bittorrent");
    expect(init.body).toBe(file);
  });

  it("loads the detail and the paginated files", async () => {
    const fetchMock = mockFetch({});

    await getTorrent("a/b");
    await getTorrentFiles("a/b", 10, 50, "movie");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/torrents/a%2Fb");
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/torrents/a%2Fb/files?offset=10&limit=50&q=movie",
    );
  });

  it("patches file priorities", async () => {
    const fetchMock = mockFetch({ id: "abc", priorities: [0, 4] });

    await setFilePriorities("abc", { only: 1 });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/torrents/abc/files");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ only: 1 }));
  });

  it("patches the session limits", async () => {
    const fetchMock = mockFetch({
      max_download_speed: 512,
      max_upload_speed: 128,
    });

    await setSessionLimits({ max_download_speed: 512, max_upload_speed: 128 });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/session/limits");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(
      JSON.stringify({ max_download_speed: 512, max_upload_speed: 128 }),
    );
  });

  it("patches the torrent limits", async () => {
    const fetchMock = mockFetch({
      id: "abc",
      max_download_speed: 0,
      max_upload_speed: -1,
    });

    await setTorrentLimits("abc", { max_download_speed: 0 });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/torrents/abc/limits");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ max_download_speed: 0 }));
  });

  it("adds and removes a label", async () => {
    const fetchMock = mockFetch({ id: "film" });

    await addLabel("film");
    await removeLabel("film");

    const [addPath, addInit] = fetchMock.mock.calls[0];
    expect(addPath).toBe("/api/labels");
    expect(addInit.method).toBe("POST");
    expect(addInit.body).toBe(JSON.stringify({ id: "film" }));

    const [removePath, removeInit] = fetchMock.mock.calls[1];
    expect(removePath).toBe("/api/labels/film");
    expect(removeInit.method).toBe("DELETE");
  });

  it("reannounces a torrent", async () => {
    const fetchMock = mockFetch({ id: "abc", reannounced: true });

    await reannounceTorrent("abc");

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/torrents/abc/reannounce");
    expect(init.method).toBe("POST");
  });

  it("moves a torrent to a new location", async () => {
    const fetchMock = mockFetch({
      id: "abc",
      destination: "/data/new",
      moving: true,
    });

    await moveTorrent("abc", "/data/new");

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/torrents/abc/move");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ location: "/data/new" }));
  });

  it("loads the labels", async () => {
    const fetchMock = mockFetch({ labels: [], no_label: 0 });

    await getLabels();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/labels");
  });
});

describe("auth", () => {
  it("loads the auth modes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ mode: "both", modes: ["token", "password"], token_set: true }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAuthInfo()).resolves.toMatchObject({
      mode: "both",
      token_set: true,
    });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth");
  });

  it("posts the credentials and returns the session token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ token: "sess", username: "admin", level: 10, expires: 1 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(login("admin", "pw")).resolves.toMatchObject({ token: "sess" });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/login");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ username: "admin", password: "pw" }));
  });

  it("lists and revokes push subscriptions", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(() => Promise.resolve(jsonResponse({ subscriptions: [] })));
    vi.stubGlobal("fetch", fetchMock);

    await getPushSubscriptions();
    await removePushSubscription("abc");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/push/subscriptions");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/push/subscriptions");
    expect(fetchMock.mock.calls[1][1].method).toBe("DELETE");
    expect(fetchMock.mock.calls[1][1].body).toBe(
      JSON.stringify({ id: "abc" }),
    );
  });

  it("signals a stale cached API response", async () => {
    const response = new Response(JSON.stringify({}), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "X-MobileUi-Stale": "1",
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    const listener = vi.fn();
    window.addEventListener("mobileui:stale", listener);

    await getSession();

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("mobileui:stale", listener);
  });

  it("logs out with the bearer token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ ok: true, session: true }));
    vi.stubGlobal("fetch", fetchMock);
    setToken("sess");

    await logout();

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/logout");
    expect(init.method).toBe("POST");
    const headers = init.headers as Headers;
    expect(headers.get("authorization")).toBe("Bearer sess");
  });
});
