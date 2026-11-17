import { describe, expect, it } from "vitest";

import { extractMagnet } from "./share";

const magnet = "magnet:?xt=urn:btih:deadbeef&dn=Demo";

describe("extractMagnet", () => {
  it("finds the magnet in the text parameter", () => {
    const search = `?text=${encodeURIComponent(`Nézd meg: ${magnet}`)}`;

    expect(extractMagnet(search)).toBe(magnet);
  });

  it("finds the magnet in the url parameter", () => {
    const search = `?url=${encodeURIComponent(magnet)}&title=Demo`;

    expect(extractMagnet(search)).toBe(magnet);
  });

  it("finds the magnet in the title parameter", () => {
    const search = `?title=${encodeURIComponent(magnet)}`;

    expect(extractMagnet(search)).toBe(magnet);
  });

  it("returns an empty string without a magnet", () => {
    expect(extractMagnet("?text=https%3A%2F%2Fexample.com&title=x")).toBe("");
    expect(extractMagnet("")).toBe("");
  });
});
