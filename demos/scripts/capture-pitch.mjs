// Records live Dana AI footage for the pitch video with Playwright.
// Token: DANA_JWT env var, or ~/.config/dana-demo/jwt (kept outside the repo).
// Usage: node scripts/capture-pitch.mjs [train-agent | lookup-agent | jobs-ui ...]
import { chromium } from "playwright";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const footageDir = join(here, "..", "public", "footage");
const APP = process.env.DANA_APP_URL ?? "http://localhost:3000";
const VIEW = { width: 1600, height: 1000 };
const DEFAULT_ANSWER = "Use the most sensible default for my data.";
const TRAIN_PROMPT = "Train an MMM model on my data.";
const LOOKUP_PROMPT = "What is the status of my last training job?";

const token =
  process.env.DANA_JWT ?? (await readFile(join(homedir(), ".config", "dana-demo", "jwt"), "utf8")).trim();
if (!token) {
  console.error("No token: set DANA_JWT or create ~/.config/dana-demo/jwt");
  process.exit(1);
}

const SEGMENTS = {
  "train-agent": async (page, log) => {
    await openChat(page);
    await sendPrompt(page, TRAIN_PROMPT);
    await driveChat(page, log, 20 * 60_000);
  },
  "lookup-agent": async (page, log) => {
    await openChat(page);
    await sendPrompt(page, LOOKUP_PROMPT);
    await driveChat(page, log, 4 * 60_000);
  },
  "jobs-ui": async (page, log) => {
    await page.goto(`${APP}/jobs`, { waitUntil: "networkidle" });
    const row = page.locator('tr[id^="job-row-"]').first();
    await row.waitFor({ timeout: 30_000 });
    await page.waitForTimeout(2000);
    await row.click();
    log.push({ at: new Date().toISOString(), step: "opened first job" });
    await page.waitForTimeout(3500);
    const next = page.getByRole("button", { name: "Next job" });
    if (await next.isEnabled().catch(() => false)) {
      await next.click();
      log.push({ at: new Date().toISOString(), step: "next job" });
      await page.waitForTimeout(3000);
    }
    await page.getByRole("button", { name: "Close job details" }).click();
    log.push({ at: new Date().toISOString(), step: "closed details" });
    await page.waitForTimeout(2500);
  },
};

async function openChat(page) {
  await page.goto(`${APP}/chat`, { waitUntil: "networkidle" });
  await composer(page).waitFor({ timeout: 30_000 });
}

function composer(page) {
  return page.locator('textarea[aria-label="Message Dana"]');
}

async function sendPrompt(page, prompt) {
  await composer(page).fill(prompt);
  await composer(page).press("Enter");
  await page.waitForTimeout(1500);
}

async function answerPending(page, log) {
  const card = page.locator('section[aria-label="Approval required"]').first();
  if (!(await card.isVisible().catch(() => false))) return false;
  const question = (await card.innerText()).slice(0, 600);
  const answer = { at: new Date().toISOString(), kind: "hitl", question, picked: [] };
  const groups = card.locator('[role="group"][aria-label="Your answer"]');
  const textbox = card.locator('textarea[aria-label="Your answer"]');
  const numeric = card.locator('input[aria-label="Your answer"]');
  for (let i = 0; i < (await groups.count()); i++) {
    const buttons = groups.nth(i).locator("button");
    const labels = await buttons.allInnerTexts();
    const index = Math.max(0, labels.findIndex((label) => !/specify|other|custom/i.test(label)));
    if ((await buttons.nth(index).getAttribute("aria-pressed")) !== "true") await buttons.nth(index).click();
    answer.picked.push(labels[index]);
  }
  if ((await groups.count()) === 0 && (await numeric.count())) {
    answer.typed = "1";
    await numeric.fill("1");
  } else if (await textbox.count()) {
    answer.typed = DEFAULT_ANSWER;
    await textbox.fill(DEFAULT_ANSWER);
  }
  const approve = card.getByRole("button", { name: "Approve", exact: true });
  if (await approve.count()) await approve.click();
  await page.waitForTimeout(800);
  await card.getByRole("button", { name: "Submit", exact: true }).click();
  log.push(answer);
  await page.waitForTimeout(2000);
  return true;
}

async function driveChat(page, log, timeoutMs) {
  const start = Date.now();
  let last = "";
  let stableSince = Date.now();
  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(1500);
    if (await answerPending(page, log)) continue;
    const text = await page.locator("main").innerText().catch(() => "");
    if (text !== last) {
      last = text;
      stableSince = Date.now();
    }
    const busy = await composer(page).isDisabled().catch(() => false);
    if (!busy && Date.now() - stableSince > 8000) return;
  }
  log.push({ at: new Date().toISOString(), step: "timed out waiting for chat to finish" });
}

const wanted = process.argv.slice(2);
const names = wanted.length ? wanted : Object.keys(SEGMENTS);
const unknown = names.filter((n) => !SEGMENTS[n]);
if (unknown.length) {
  console.error(`Unknown segment(s): ${unknown.join(", ")}. Options: ${Object.keys(SEGMENTS).join(", ")}`);
  process.exit(1);
}

await mkdir(join(footageDir, "logs"), { recursive: true });
const browser = await chromium.launch();

for (const name of names) {
  const tmpDir = join(footageDir, ".tmp", name);
  const context = await browser.newContext({
    viewport: VIEW,
    deviceScaleFactor: 1,
    recordVideo: { dir: tmpDir, size: VIEW },
  });
  await context.addInitScript((t) => {
    localStorage.setItem("dana.accessToken", t);
    localStorage.removeItem("dana.chatSelection");
  }, token);
  const page = await context.newPage();
  const log = [];
  const started = Date.now();
  console.log(`recording ${name}...`);
  await SEGMENTS[name](page, log);
  await page.waitForTimeout(1500);
  const video = page.video();
  await context.close();
  const file = join(footageDir, `${name}.webm`);
  await rename(await video.path(), file);
  await rm(tmpDir, { recursive: true, force: true });
  log.push({ step: "segment done", seconds: Math.round((Date.now() - started) / 1000) });
  await writeFile(join(footageDir, "logs", `${name}.json`), JSON.stringify(log, null, 2));
  console.log(`wrote ${file} (${log.length} log entries)`);
}

await browser.close();
