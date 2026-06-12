import { expect, test } from "@playwright/test";

test("login page loads and shows Anmeldung", async ({ page }) => {
  const response = await page.goto("/login");
  expect(response?.status()).toBeLessThan(500);
  await expect(page.getByText(/Anmeldung/i)).toBeVisible();
});
