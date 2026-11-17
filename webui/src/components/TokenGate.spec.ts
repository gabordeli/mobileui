import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";

import { setLocale, t } from "../i18n";
import TokenGate from "./TokenGate.vue";

beforeEach(() => setLocale("en"));

function factory(overrides: Record<string, unknown> = {}) {
  return mount(TokenGate, {
    props: {
      modes: ["token"],
      initialToken: "",
      error: "",
      cancelable: false,
      pluginVersion: "0.1.3",
      tokenSet: true,
      ...overrides,
    },
  });
}

describe("TokenGate", () => {
  it("submits the trimmed token and shows the plugin version", async () => {
    const wrapper = factory({ initialToken: "  secret  " });
    expect(wrapper.text()).toContain("MobileUi v0.1.3");

    await wrapper.get("input").setValue("  abc  ");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")?.[0]).toEqual([
      { mode: "token", token: "abc" },
    ]);
  });

  it("submits the username and password in password mode", async () => {
    const wrapper = factory({ modes: ["password"] });
    const inputs = wrapper.findAll("input");

    await inputs[0].setValue("  admin  ");
    await inputs[1].setValue("pw");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")?.[0]).toEqual([
      { mode: "password", username: "admin", password: "pw" },
    ]);
  });

  it("switches between the password and token tabs", async () => {
    const wrapper = factory({ modes: ["token", "password"] });
    const tabs = wrapper.findAll('[role="tab"]');
    expect(tabs).toHaveLength(2);
    expect(tabs[0].attributes("aria-selected")).toBe("true");

    await tabs[1].trigger("click");

    expect(wrapper.findAll("input")).toHaveLength(1);
    expect(tabs[1].attributes("aria-selected")).toBe("true");
  });

  it("shows an error and emits cancel when cancelable", async () => {
    const wrapper = factory({ error: "bad token", cancelable: true });
    expect(wrapper.get('[role="alert"]').text()).toBe("bad token");

    const cancel = wrapper
      .findAll("button")
      .find((button) => button.text() === t("token.cancel"));
    expect(cancel).toBeDefined();
    await cancel!.trigger("click");

    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });

  it("hides the cancel button and the error by default", () => {
    const wrapper = factory();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.findAll("button")).toHaveLength(1);
  });

  it("hints when no token is configured", () => {
    const wrapper = factory({ tokenSet: false });
    expect(wrapper.text()).toContain(t("auth.noToken"));
  });

  it("shows the signed-in user and emits logout", async () => {
    const wrapper = factory({ username: "admin", level: 10 });
    expect(wrapper.text()).toContain(t("auth.loggedIn", { user: "admin" }));
    expect(wrapper.text()).not.toContain(t("auth.readonly"));

    const logout = wrapper
      .findAll("button")
      .find((button) => button.text() === t("auth.logout"));
    await logout!.trigger("click");

    expect(wrapper.emitted("logout")).toHaveLength(1);
  });

  it("marks a read-only account", () => {
    const wrapper = factory({ username: "guest", level: 1 });
    expect(wrapper.text()).toContain(t("auth.readonly"));
  });

  it("labels the static token identity", () => {
    const wrapper = factory({ username: "token", level: 10 });
    expect(wrapper.text()).toContain(t("auth.loggedIn", { user: "API token" }));
  });
});
