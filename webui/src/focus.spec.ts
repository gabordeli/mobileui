import { afterEach, describe, expect, it } from "vitest";

import { trapFocus } from "./focus";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("trapFocus", () => {
  it("cycles Tab inside the container and restores focus", () => {
    const app = document.createElement("div");
    app.id = "app";
    const previous = document.createElement("button");
    previous.textContent = "previous";
    const container = document.createElement("div");
    const first = document.createElement("button");
    const last = document.createElement("button");
    first.textContent = "first";
    last.textContent = "last";
    container.append(first, last);
    document.body.append(previous, app, container);
    previous.focus();

    const release = trapFocus(container);

    expect(document.activeElement).toBe(first);
    expect(app.hasAttribute("inert")).toBe(true);

    last.focus();
    container.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Tab", bubbles: true }),
    );
    expect(document.activeElement).toBe(first);

    first.focus();
    container.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Tab",
        shiftKey: true,
        bubbles: true,
      }),
    );
    expect(document.activeElement).toBe(last);

    release();

    expect(app.hasAttribute("inert")).toBe(false);
    expect(document.activeElement).toBe(previous);
  });
});
