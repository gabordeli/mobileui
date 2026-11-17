import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  UnauthorizedError,
  addTorrentMagnet,
  eventsUrl,
  getHealth,
  getSession,
  getToken,
  listTorrents,
  setToken,
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
