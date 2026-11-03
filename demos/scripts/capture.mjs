// Captures real Dana AI outputs with Playwright for the demo videos.
// Usage: DANA_JWT=<token> node scripts/capture.mjs [scene-id ...]
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, "..", "public", "captures");
const APP = process.env.DANA_APP_URL ?? "http://localhost:3000";
const token = process.env.DANA_JWT;
if (!token) {
  console.error("Set DANA_JWT to a valid access token.");
  process.exit(1);
}

const SCENES = [
  { id: "date-tool", prompt: "What is today's date and the current time in IST?" },
  { id: "math-tool", prompt: "Calculate 12.5% of 480, then add 37." },
  { id: "holidays-tool", prompt: "List the public holidays in India for the rest of this year." },
  { id: "connectors", prompt: "What data connectors do I have connected?" },
  { id: "job-status", prompt: "What is the status of my last training job?" },
  { id: "model-location", prompt: "Where is my latest trained model saved?" },
  { id: "train-hitl", prompt: "Train an MMM model on my data." },
];

const PAGES = [
  { id: "jobs-page", path: "/jobs" },
  { id: "connectors-page", path: "/connectors" },
];

const wanted = process.argv.slice(2);
const scenes = wanted.length ? SCENES.filter((s) => wanted.includes(s.id)) : SCENES;
const pages = wanted.length ? PAGES.filter((p) => wanted.includes(p.id)) : PAGES;

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
await context.addInitScript((t) => {
  localStorage.setItem("dana.accessToken", t);
}, token);

await mkdir(outDir, { recursive: true });
const transcript = [];

async function waitForIdle(page, timeoutMs = 240_000) {
  const start = Date.now();
  let last = "";
  let stableSince = Date.now();
  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(1000);
    const text = await page.locator("main").innerText().catch(() => "");
    if (text !== last) {
      last = text;
      stableSince = Date.now();
    }
    const busy = await page.locator('textarea[aria-label="Message Dana"]').isDisabled().catch(() => false);
    if (!busy && Date.now() - stableSince > 4000) return;
  }
}

for (const scene of scenes) {
  const page = await context.newPage();
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.addInitScript(() => localStorage.removeItem("dana.chatSelection"));
  await page.goto(`${APP}/chat`, { waitUntil: "networkidle" });
  const composer = page.locator('textarea[aria-label="Message Dana"]');
  await composer.waitFor({ timeout: 30_000 });
  await composer.fill(scene.prompt);
  await composer.press("Enter");
  await page.waitForTimeout(1500);
  await waitForIdle(page);
  await page.screenshot({ path: join(outDir, `${scene.id}.png`) });
  const text = await page.locator("main").innerText();
  transcript.push({ id: scene.id, prompt: scene.prompt, output: text });
  console.log(`captured ${scene.id}`);
  await page.close();
}

if (scenes.length) await writeFile(join(outDir, "transcript.json"), JSON.stringify(transcript, null, 2));

for (const p of pages) {
  const page = await context.newPage();
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${APP}${p.path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(outDir, `${p.id}.png`) });
  console.log(`captured ${p.id}`);
  await page.close();
}
await browser.close();
console.log(`wrote ${transcript.length} scenes to ${outDir}`);
