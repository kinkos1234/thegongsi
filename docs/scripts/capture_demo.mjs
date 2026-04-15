#!/usr/bin/env node
// Demo screenshot capture via Playwright.
// Usage:
//   cd docs && npm install playwright
//   node scripts/capture_demo.mjs
//
// Expects frontend on localhost:3333 and backend on localhost:8888.

import { chromium } from "playwright";
import { mkdir } from "fs/promises";
import { resolve } from "path";

const OUT_DIR = resolve(new URL(".", import.meta.url).pathname, "..", "screenshots");
const BASE = process.env.COMAD_BASE || "http://localhost:3333";

const shots = [
  { name: "01-landing", url: "/", viewport: { width: 1440, height: 1800 }, fullPage: true },
  { name: "02-login", url: "/login", viewport: { width: 1440, height: 900 } },
  { name: "03-ask-empty", url: "/ask", viewport: { width: 1440, height: 900 } },
  { name: "04-ask-answer", url: "/ask", viewport: { width: 1440, height: 1200 }, action: async (page) => {
      await page.fill('input[placeholder*="HBM"]', "이재용이 이끄는 회사");
      await page.click('button[type="submit"]');
      await page.waitForSelector("[class*='border-accent']", { timeout: 30000 });
      await page.waitForTimeout(500);
    } },
  { name: "05-company-dashboard", url: "/c/005930", viewport: { width: 1440, height: 1600 }, fullPage: true },
  { name: "06-404", url: "/c/000000", viewport: { width: 1440, height: 900 } },
  { name: "07-watchlist-empty", url: "/watchlist", viewport: { width: 1440, height: 900 } },
];

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();

  for (const s of shots) {
    const context = await browser.newContext({ viewport: s.viewport });
    const page = await context.newPage();
    console.log(`→ ${s.name}`);
    await page.goto(`${BASE}${s.url}`, { waitUntil: "networkidle", timeout: 30000 });
    if (s.action) await s.action(page);
    await page.screenshot({
      path: resolve(OUT_DIR, `${s.name}.png`),
      fullPage: s.fullPage || false,
    });
    await context.close();
  }

  await browser.close();
  console.log(`\n✓ Screenshots → ${OUT_DIR}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
