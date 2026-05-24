import { expect, test, type Page } from "@playwright/test";

async function mockCommonApi(page: Page) {
  await page.route("**/api/csrf", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ csrf_token: "test-csrf" }) })
  );
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: "test-access-token" }) })
  );
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        email: "owner@example.test",
        name: "Owner",
        role: "owner",
        locale: "hu",
        theme: "light",
        tenant_kb_has_training: true,
      }),
    })
  );
  await page.route("**/api/auth/default-settings", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ locale: "hu", theme: "light" }) })
  );
  await page.route("**/api/settings", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        two_factor_enabled: false,
        timezone: "Europe/Budapest",
        date_format: "YYYY-MM-DD",
        time_format: "HH:mm",
      }),
    })
  );
}

async function mockKnowledgeApi(page: Page) {
  await page.route("**/api/kb", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          uuid: "kb-1",
          name: "Smoke KB",
          description: "",
          status: "active",
          can_train: true,
          storage_metrics: { total_bytes: 0, file_bytes: 0, database_bytes: 0, qdrant_bytes: 0, training_char_count: 1200 },
        },
      ]),
    })
  );
  await page.route("**/api/kb/*/ingest-runs/run-1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "run-1",
        kb_uuid: "kb-1",
        status: "running",
        total_items: 1,
        processed_items: 0,
        failed_items: 0,
        items: [],
        logs: [],
      }),
    })
  );
}

test.beforeEach(async ({ page }) => {
  await mockCommonApi(page);
  await mockKnowledgeApi(page);
});

test("login oldal betölt", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: /belép|login|sign in/i })).toBeVisible();
});

test("védett route loginra redirectel token nélkül", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
  await page.goto("/admin/tudastar");
  await expect(page).toHaveURL(/\/login/);
});

test("mockolt login után KB lista renderel", async ({ page }) => {
  await page.goto("/admin/tudastar");
  await expect(page.getByText("Smoke KB").first()).toBeVisible();
});

test("chat oldal renderel", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByText("Smoke KB").first()).toBeVisible();
});

test("permission denied oldal működik admin felhasználóval owner-only route-on", async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 2, email: "admin@example.test", role: "admin", locale: "hu", theme: "light" }),
    })
  );
  await page.goto("/admin/settings");
  await expect(page.getByText("Nincs jogosultságod az oldal megtekintéséhez.")).toBeVisible();
});

test("platform-admin login oldal renderel", async ({ page }) => {
  await page.goto("/platform-admin/login");
  await expect(page.getByRole("button", { name: /belép|login/i })).toBeVisible();
});
