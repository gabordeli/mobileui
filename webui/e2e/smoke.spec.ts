import { expect, test, type Page } from "@playwright/test";

const health = { ok: true, version: "0.1.3", port: 8113 };

const session = {
  download_rate: 0,
  upload_rate: 0,
  payload_download_rate: 0,
  payload_upload_rate: 0,
  num_torrents: 1,
  paused: false,
  free_space: 8 * 1024 ** 3,
  version: "2.2.0",
  download_location: "/downloads",
  queue: {},
};

const labels = { labels: [], no_label: 1 };

const torrent = {
  id: "demo-movie",
  name: "Demo Movie 2024",
  state: "Paused",
  progress: 0,
  label: "No Label",
  download_payload_rate: 0,
  upload_payload_rate: 0,
  eta: 0,
  ratio: 0,
  total_size: 734003200,
  save_path: "/downloads",
};

const torrentList = { total: 1, offset: 0, limit: 50, torrents: [torrent] };

const detail = {
  ...torrent,
  total_done: 0,
  total_uploaded: 0,
  total_payload_download: 0,
  total_payload_upload: 0,
  download_location: "/downloads",
  num_peers: 0,
  num_seeds: 0,
  total_peers: 0,
  total_seeds: 0,
  is_finished: false,
  is_seed: false,
  time_added: 1763380000,
  tracker: "",
  tracker_host: "",
  comment: "",
  creator: "",
  num_files: 1,
  num_pieces: 0,
  piece_length: 0,
  private: false,
  queue: 0,
  message: "OK",
  active_time: 0,
  seeding_time: 0,
  finished_time: 0,
};

const files = {
  total: 1,
  offset: 0,
  limit: 50,
  files: [
    { index: 0, path: "demo-movie.mkv", size: 734003200, offset: 0, progress: 0 },
  ],
};

const authTokenOnly = { mode: "token", modes: ["token"], token_set: true };

async function mockApi(
  page: Page,
  options: { auth?: Record<string, unknown> } = {},
): Promise<void> {
  await page.route("**/health", (route) => route.fulfill({ json: health }));
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());

    if (url.pathname === "/api/events") {
      return route.abort();
    }
    if (url.pathname === "/api/auth") {
      return route.fulfill({ json: options.auth ?? authTokenOnly });
    }
    if (url.pathname === "/api/login") {
      return route.fulfill({
        json: { token: "sess", username: "admin", level: 10, expires: 1 },
      });
    }

    const auth = route.request().headers()["authorization"] ?? "";
    if (auth === "Bearer ") {
      return route.fulfill({ status: 401, json: {} });
    }
    switch (url.pathname) {
      case "/api/session":
        return route.fulfill({ json: session });
      case "/api/labels":
        return route.fulfill({ json: labels });
      case "/api/torrents":
        return route.fulfill({ json: torrentList });
      case "/api/torrents/demo-movie":
        return route.fulfill({ json: detail });
      case "/api/torrents/demo-movie/files":
        return route.fulfill({ json: files });
      default:
        return route.fulfill({ status: 404, json: { message: "not found" } });
    }
  });
}

test("token gate accepts a valid token", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await expect(page.getByPlaceholder("API token")).toBeVisible();
  await page.getByPlaceholder("API token").fill("dev-token");
  await page.getByRole("button", { name: "Belépés" }).click();

  await expect(
    page.getByRole("button", { name: "Demo Movie 2024" }),
  ).toBeVisible();
});

test("account login accepts username and password", async ({ page }) => {
  await mockApi(page, {
    auth: { mode: "both", modes: ["token", "password"], token_set: true },
  });
  await page.goto("/");

  await expect(page.getByRole("tab", { name: "Fiók" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByPlaceholder("Felhasználónév").fill("admin");
  await page.getByPlaceholder("Jelszó").fill("pw");
  await page.getByRole("button", { name: "Belépés" }).click();

  await expect(
    page.getByRole("button", { name: "Demo Movie 2024" }),
  ).toBeVisible();
});

test("read-only account hides the write actions", async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("mobileui.token", "dev-token"),
  );
  await mockApi(page, {
    auth: {
      mode: "password",
      modes: ["password"],
      token_set: false,
      authenticated: true,
      username: "guest",
      level: 1,
      write: false,
    },
  });
  await page.goto("/");

  await expect(
    page.getByRole("button", { name: "Demo Movie 2024" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Torrent hozzáadása" }),
  ).toHaveCount(0);
});

test.describe("authenticated UI", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() =>
      localStorage.setItem("mobileui.token", "dev-token"),
    );
    await mockApi(page);
    await page.goto("/");
  });

  test("lists torrents and opens the detail", async ({ page }) => {
    const row = page.getByRole("button", { name: "Demo Movie 2024" });
    await expect(row).toBeVisible();
    await row.click();

    const dialog = page.getByRole("dialog", { name: "Torrent részletek" });
    await expect(dialog).toBeVisible();
    await expect(
      dialog.getByRole("heading", { name: "Demo Movie 2024" }),
    ).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Folytatás" })).toBeVisible();
  });

  test("opens the session sheet", async ({ page }) => {
    await page.getByRole("button", { name: "Munkamenet adatai" }).click();

    const dialog = page.getByRole("dialog", { name: "Munkamenet" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Szabad hely")).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: "Összes szüneteltetése" }),
    ).toBeVisible();
  });

  test("opens the add sheet", async ({ page }) => {
    await page.getByRole("button", { name: "Torrent hozzáadása" }).click();

    const dialog = page.getByRole("dialog", { name: "Torrent hozzáadása" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("textbox", { name: "Magnet link" })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Hozzáadás" })).toBeVisible();
  });
});
