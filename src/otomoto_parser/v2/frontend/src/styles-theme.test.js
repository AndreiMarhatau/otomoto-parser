import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const stylesDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "styles");
const themeCss = fs.readFileSync(path.join(stylesDir, "theme.css"), "utf8");
const componentStyles = ["controls.css", "listing-details.css", "modals.css"].map((name) => ({
  name,
  content: fs.readFileSync(path.join(stylesDir, name), "utf8"),
}));

describe("frontend theme tokens", () => {
  it("defines key semantic tokens for both light and dark themes", () => {
    for (const token of [
      "--focus-ring",
      "--overlay-backdrop",
      "--success-bg",
      "--success-text",
      "--warning-bg",
      "--warning-text",
      "--danger-bg",
      "--danger-text",
      "--chip-price-bg",
      "--chip-price-text",
      "--chip-verified-bg",
      "--chip-verified-text",
      "--chip-engine-bg",
      "--chip-engine-text",
      "--chip-year-bg",
      "--chip-year-text",
      "--chip-mileage-bg",
      "--chip-mileage-text",
      "--chip-drive-bg",
      "--chip-drive-text",
      "--category-count-bg",
      "--report-state-success",
      "--report-state-failed",
    ]) {
      expect(themeCss).toContain(`${token}:`);
      expect(themeCss).toMatch(new RegExp(`@media \\(prefers-color-scheme: dark\\)[\\s\\S]*${token}:`));
    }
  });

  it("keeps component styles token-driven for key interactive and status surfaces", () => {
    expect(componentStyles.find((entry) => entry.name === "controls.css")?.content).toContain("var(--focus-ring)");
    expect(componentStyles.find((entry) => entry.name === "controls.css")?.content).toContain("var(--chip-price-bg)");
    expect(componentStyles.find((entry) => entry.name === "controls.css")?.content).toContain("var(--chip-price-text)");
    expect(componentStyles.find((entry) => entry.name === "listing-details.css")?.content).toContain("var(--category-count-bg)");
    expect(componentStyles.find((entry) => entry.name === "listing-details.css")?.content).toContain("var(--report-state-success)");
    expect(componentStyles.find((entry) => entry.name === "listing-details.css")?.content).toContain("var(--report-state-failed)");
    expect(componentStyles.find((entry) => entry.name === "modals.css")?.content).toContain("var(--overlay-backdrop)");
  });
});
