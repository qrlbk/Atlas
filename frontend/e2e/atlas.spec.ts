import { test, expect } from "@playwright/test";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:18080";
const ADMIN_EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? "admin@atlas.example.com";
const ADMIN_PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? "AtlasSeed!2026";

test.describe("Atlas MVP", () => {
  test("seeded reference data is reachable via API", async ({ request }) => {
    const login = await request.post(`${API_URL}/auth/login`, {
      json: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD }
    });
    expect(login.ok(), await login.text()).toBeTruthy();
    const { access_token: token } = (await login.json()) as { access_token: string };

    const subjects = await request.get(`${API_URL}/subjects`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    expect(subjects.ok()).toBeTruthy();
    const subjectRows = (await subjects.json()) as { name: string }[];
    expect(subjectRows.length).toBeGreaterThanOrEqual(4);
    expect(subjectRows.some((s) => s.name === "Mathematics")).toBeTruthy();

    const slots = await request.get(`${API_URL}/lesson-slots`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    expect(slots.ok()).toBeTruthy();
    const slotRows = (await slots.json()) as unknown[];
    expect(slotRows.length).toBeGreaterThanOrEqual(35);
  });

  test("UI login, CRUD teacher, schedule surface", async ({ page, browserName }) => {
    await page.goto("/");
    await page.evaluate(() => localStorage.clear());
    await page.reload();

    await page.getByTestId("login-email").fill(ADMIN_EMAIL);
    await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("login-status")).toBeVisible();

    const name = `E2E Teacher ${browserName}-${Date.now()}`;
    await page.getByTestId("teacher-full-name").fill(name);
    await page.getByTestId("teacher-submit").click();
    await expect(page.getByTestId("teacher-list")).toContainText(name);

    const row = page.getByTestId("teacher-list").locator("li").filter({ hasText: name });
    await row.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByTestId("teacher-list")).not.toContainText(name);

    await expect(page.getByTestId("schedule-builder")).toBeVisible();
    await expect(page.getByTestId("teacher-analytics")).toBeVisible();
  });

  test("UI classroom PATCH flow", async ({ page, browserName }) => {
    const login = await page.request.post(`${API_URL}/auth/login`, {
      json: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD }
    });
    expect(login.ok()).toBeTruthy();
    const { access_token: token } = (await login.json()) as { access_token: string };

    const schools = await page.request.get(`${API_URL}/schools`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    expect(schools.ok()).toBeTruthy();
    const schoolList = (await schools.json()) as { id: number }[];
    const schoolId = schoolList[0]?.id ?? 1;

    const roomNumber = `E2E-${browserName}-${Date.now()}`;
    const created = await page.request.post(`${API_URL}/classrooms`, {
      headers: { Authorization: `Bearer ${token}` },
      json: {
        room_number: roomNumber,
        capacity: 20,
        specialization: "standard",
        school_id: schoolId
      }
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const classroom = (await created.json()) as { id: number };

    await page.addInitScript((t) => localStorage.setItem("atlas_access_token", t), token);
    await page.goto("/");
    await expect(page.getByTestId(`classroom-row-${classroom.id}`)).toContainText(roomNumber);

    await page.getByTestId(`edit-classroom-${classroom.id}`).click();
    await page.getByTestId("classroom-capacity").fill("25");
    await page.getByTestId("classroom-submit").click();
    await expect(page.getByTestId(`classroom-row-${classroom.id}`)).toContainText("(25)");

    await page.getByTestId(`delete-classroom-${classroom.id}`).click();
    await expect(page.getByTestId("classroom-list")).not.toContainText(roomNumber);
  });
});
