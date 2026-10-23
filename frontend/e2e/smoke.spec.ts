import { expect, test } from "@playwright/test";

test("login page loads and offers the sign-in action", async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Unauthorized" }),
    }),
  );
  const response = await page.goto("/login");
  expect(response?.status()).toBeLessThan(500);
  await expect(page.getByRole("button", { name: "Anmelden" })).toBeVisible();
  await expect(page.getByText("Melde dich an, um fortzufahren")).toBeVisible();
});
