const puppeteerCore = require("puppeteer-core");
const { addExtra } = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");

const puppeteer = addExtra(puppeteerCore);
puppeteer.use(StealthPlugin());

const CHROMIUM_PATH = process.env.CHROMIUM_PATH || undefined;
const HEADLESS = process.env.HEADLESS !== "false";
const REALISTIC_USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const UA_METADATA = {
  brands: [
    { brand: "Not_A Brand", version: "8" },
    { brand: "Chromium", version: "120" },
    { brand: "Google Chrome", version: "120" },
  ],
  fullVersion: "120.0.6099.131",
  fullVersionList: [
    { brand: "Not_A Brand", version: "8.0.0.0" },
    { brand: "Chromium", version: "120.0.6099.131" },
    { brand: "Google Chrome", version: "120.0.6099.131" },
  ],
  platform: "macOS",
  platformVersion: "14.0.0",
  architecture: "arm",
  bitness: "64",
  wow64: false,
  model: "",
  mobile: false,
};

async function startLogin(gatewayUrl, username, password, mode) {
  const loginMode = _normalizeMode(mode);
  const launchOptions = {
    headless: HEADLESS ? "new" : false,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--ignore-certificate-errors",
      "--disable-blink-features=AutomationControlled",
      "--lang=en-US,en",
    ],
    ignoreDefaultArgs: ["--enable-automation"],
  };
  if (CHROMIUM_PATH) launchOptions.executablePath = CHROMIUM_PATH;

  const browser = await puppeteer.launch(launchOptions);
  const page = await browser.newPage();
  await _applyHumanFingerprint(page);

  await page.goto(gatewayUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await _capture(page, "step_01_after_goto");
  await _humanPause(1500, 3000);

  await page.waitForSelector(
    'input[name="username"], input#user_name, input[name="loginId"]',
    { timeout: 15_000 }
  );
  await _capture(page, "step_02_form_ready");

  if (loginMode === "paper") {
    await _selectPaperMode(page);
    await _capture(page, "step_03_paper_selected");
  }

  await _fillCredentials(page, username, password);
  await _capture(page, "step_04_credentials_filled");
  console.log("[login] URL before submit:", page.url());

  await _submitForm(page);
  await _humanPause(2000, 3500);
  await _capture(page, "step_05_just_after_submit");
  await new Promise((r) => setTimeout(r, 5000));
  await _capture(page, "step_06_after_submit_5s");

  console.log("[login] URL after submit:", page.url());

  const bodyText = await page.evaluate(() => document.body?.innerText || "");
  console.log("[login] body after submit:", bodyText.substring(0, 200));

  const isSuccess = _checkSuccess(bodyText);
  if (isSuccess) {
    await browser.close();
    return { session: null, status: "authenticated" };
  }

  const method = _detectTwoFactorMethod(bodyText);
  if (method === "sms") {
    console.log("[login] SMS 2FA page detected");
    return { session: { browser, page }, status: "2fa_required", method: "sms", challenge_code: null };
  }
  if (method === "challenge_response") {
    await _selectChallengeResponse(page);
    const challengeCode = await _extractChallengeCode(page);
    return { session: { browser, page }, status: "2fa_required", method: "challenge_response", challenge_code: challengeCode };
  }

  await page.screenshot({ path: "/tmp/login_02_failed.png", fullPage: true });
  await browser.close();
  return { session: null, status: "failed", error: "No 2FA page and no success", body: bodyText.substring(0, 300) };
}

function _detectTwoFactorMethod(bodyText) {
  if (bodyText.includes("Resend SMS") || bodyText.includes("security code")) {
    return "sms";
  }
  if (
    bodyText.includes("Challenge/Response") ||
    bodyText.includes("Second Factor") ||
    bodyText.includes("Select Type") ||
    bodyText.includes("QR Code")
  ) {
    return "challenge_response";
  }
  return "unknown";
}

function _normalizeMode(mode) {
  const value = String(mode || "live")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  if (["live", "real", "prod", "production"].includes(value)) return "live";
  if (["paper", "simulated", "simulation", "simule", "demo"].includes(value)) {
    return "paper";
  }
  throw new Error(`Unsupported login mode: ${mode}`);
}

async function submit2FA(session, code) {
  const { browser, page } = session;

  await page.screenshot({ path: "/tmp/2fa_01_before_fill.png", fullPage: true });
  console.log("[2fa] screenshot: /tmp/2fa_01_before_fill.png");

  const filled = await page.evaluate((c) => {
    const inputs = [...document.querySelectorAll("input")];
    const target = inputs.find(
      (i) =>
        i.type !== "hidden" &&
        i.type !== "checkbox" &&
        i.name !== "username" &&
        i.name !== "loginId" &&
        i.name !== "password" &&
        i.offsetParent !== null
    );
    if (!target) return null;
    target.focus();
    target.value = c;
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }, code);

  console.log("[2fa] filled:", filled);
  await page.screenshot({ path: "/tmp/2fa_02_after_fill.png", fullPage: true });

  if (!filled) {
    await browser.close();
    return { status: "failed", error: "No input field found for OTP code" };
  }

  const submitted = await page.evaluate(() => {
    const btns = [...document.querySelectorAll("button, input[type='submit']")];
    const btn = btns.find(
      (b) =>
        b.offsetParent !== null &&
        (b.textContent.trim().toLowerCase().includes("login") ||
          b.textContent.trim().toLowerCase().includes("submit") ||
          b.type === "submit")
    );
    if (btn) { btn.click(); return btn.textContent.trim(); }
    return null;
  });
  console.log("[2fa] submit clicked:", submitted);
  await page.screenshot({ path: "/tmp/2fa_03_after_submit.png", fullPage: true });

  for (let i = 0; i < 12; i++) {
    await new Promise((r) => setTimeout(r, 5000));
    const bodyText = await page.evaluate(
      () => document.body?.innerText || ""
    );

    if (_checkSuccess(bodyText)) {
      await browser.close();
      return { status: "authenticated" };
    }

    if (i % 3 === 0) {
      await page.screenshot({ path: `/tmp/2fa_wait_${i * 5}s.png`, fullPage: true });
      console.log(`[2fa] ${i * 5}s - ${bodyText.substring(0, 100)}`);
    }

    const hasError = _checkError(bodyText);
    if (hasError) {
      await browser.close();
      return { status: "failed", error: "IBKR rejected the code" };
    }
  }

  await browser.close();
  return { status: "failed", error: "Timeout waiting for login after 2FA" };
}

async function resendSms(session) {
  const { page } = session;
  const result = await page.evaluate(() => {
    const candidates = [...document.querySelectorAll("a, button, span")];
    const link = candidates.find((el) =>
      el.textContent.trim().toLowerCase() === "resend sms"
    );
    if (!link) return { clicked: false, reason: "Resend SMS element not found" };
    if (link.disabled || link.getAttribute("aria-disabled") === "true") {
      return { clicked: false, reason: "Resend SMS is disabled (cooldown)" };
    }
    link.click();
    return { clicked: true };
  });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: "/tmp/sms_resend.png", fullPage: true });
  const bodyText = await page.evaluate(() => document.body?.innerText || "");
  const cooldown = bodyText.match(/request a new SMS in (\d+) seconds/);
  if (!result.clicked) {
    return { status: "failed", error: result.reason, cooldown_seconds: cooldown ? Number(cooldown[1]) : null };
  }
  console.log("[resend-sms] clicked Resend SMS");
  return { status: "ok", cooldown_seconds: cooldown ? Number(cooldown[1]) : null };
}

function destroySession(session) {
  if (!session) return;
  session.browser.close().catch(() => {});
}

function _checkSuccess(bodyText) {
  return (
    bodyText.includes("Client login succeeds") ||
    bodyText.includes("Login successful") ||
    bodyText.includes("authenticated") ||
    bodyText.includes("close the browser")
  );
}

function _checkError(bodyText) {
  return (
    bodyText.includes("Invalid") ||
    bodyText.includes("Login failed") ||
    bodyText.includes("temporarily locked") ||
    bodyText.includes("incorrect")
  );
}

async function _selectPaperMode(page) {
  const result = await page.evaluate(() => {
    const normalize = (text) => (text || "").replace(/\s+/g, " ").trim();
    const isVisible = (el) => {
      if (!el) return false;
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    };
    const labelText = (input) => {
      const explicit = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
      const wrapper = input.closest("label");
      return normalize(`${explicit?.textContent || ""} ${wrapper?.textContent || ""}`);
    };
    const elementText = (el) => normalize(`${el.textContent || ""} ${el.getAttribute("aria-label") || ""}`);
    const isPaperText = (text) => /^paper( trading)?$/i.test(text) || (/paper/i.test(text) && !/live/i.test(text) && text.length <= 50);
    const describesPaper = (el) => isPaperText(elementText(el));
    const describe = (el) => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${el.getAttribute("role") ? `[role=${el.getAttribute("role")}]` : ""}`;
    const isPaperSelected = () => {
      const paperInputs = [...document.querySelectorAll('input[type="radio"], input[type="checkbox"]')]
        .filter((input) => /paper/i.test(`${input.name || ""} ${input.id || ""} ${input.value || ""} ${labelText(input)}`));
      if (paperInputs.some((input) => input.checked)) return true;

      const selected = [...document.querySelectorAll('[aria-checked="true"], [aria-selected="true"], .active, .selected')]
        .filter(isVisible);
      return selected.some(describesPaper);
    };

    if (isPaperSelected()) return { clicked: "already", verified_before_wait: true };

    const paperInputs = [...document.querySelectorAll('input[type="radio"], input[type="checkbox"]')]
      .filter((input) => /paper/i.test(`${input.name || ""} ${input.id || ""} ${input.value || ""} ${labelText(input)}`));
    for (const input of paperInputs) {
      const explicit = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
      const target = explicit || input.closest("label") || input;
      if (!isVisible(target) && !isVisible(input)) continue;
      target.click();
      return { clicked: describe(target), verified_before_wait: isPaperSelected() };
    }

    const textCandidates = [...document.querySelectorAll("button, label, a, [role='radio'], [role='switch'], [role='tab'], span, div")]
      .filter(isVisible)
      .filter((el) => {
        const text = elementText(el);
        return isPaperText(text);
      });
    for (const el of textCandidates) {
      const target = el.closest("button, label, a, [role='radio'], [role='switch'], [role='tab']") || el;
      if (!isVisible(target)) continue;
      target.click();
      return { clicked: describe(target), verified_before_wait: isPaperSelected() };
    }

    return { clicked: null, verified_before_wait: false };
  });
  await _humanPause(500, 900);
  const verified = await page.evaluate(() => {
    const normalize = (text) => (text || "").replace(/\s+/g, " ").trim();
    const labelText = (input) => {
      const explicit = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
      const wrapper = input.closest("label");
      return normalize(`${explicit?.textContent || ""} ${wrapper?.textContent || ""}`);
    };
    const elementText = (el) => normalize(`${el.textContent || ""} ${el.getAttribute("aria-label") || ""}`);
    const isPaperText = (text) => /^paper( trading)?$/i.test(text) || (/paper/i.test(text) && !/live/i.test(text) && text.length <= 50);
    const paperInputs = [...document.querySelectorAll('input[type="radio"], input[type="checkbox"]')]
      .filter((input) => /paper/i.test(`${input.name || ""} ${input.id || ""} ${input.value || ""} ${labelText(input)}`));
    if (paperInputs.some((input) => input.checked)) return true;
    const selected = [...document.querySelectorAll('[aria-checked="true"], [aria-selected="true"], .active, .selected')];
    return selected.some((el) => isPaperText(elementText(el)));
  });
  console.log(`[login] paper selection: ${JSON.stringify({ ...result, verified })}`);
  if (!verified) {
    throw new Error(`Failed to engage Paper mode: ${JSON.stringify(result)}`);
  }
}

async function _fillCredentials(page, username, password) {
  console.log("[login] password length:", password.length);
  const userSel = await _findField(page, [
    'input[name="username"]',
    'input#user_name',
    'input[name="loginId"]',
  ]);
  await _humanClick(page, userSel);
  await _humanType(page, userSel, username);
  await _humanPause(200, 600);

  const passSel = await _findField(page, [
    'input[name="password"]',
    'input#password',
    'input[type="password"]',
  ]);
  await _humanClick(page, passSel);
  await _humanType(page, passSel, password);
  await _humanPause(300, 800);
}

async function _submitForm(page) {
  const submitSel = await _findField(page, [
    'button[type="submit"]',
    'input[type="submit"]',
    "#submitForm",
    ".btn-primary",
  ]);
  await _humanClick(page, submitSel);
}

async function _applyHumanFingerprint(page) {
  await page.setUserAgent(REALISTIC_USER_AGENT, UA_METADATA);
  await page.setExtraHTTPHeaders({ "Accept-Language": "en-US,en;q=0.9" });
  const width = 1280 + Math.floor(Math.random() * 120);
  const height = 800 + Math.floor(Math.random() * 120);
  await page.setViewport({
    width,
    height,
    deviceScaleFactor: 2,
    hasTouch: false,
    isMobile: false,
  });
}

function _randomInt(min, max) {
  return Math.floor(min + Math.random() * (max - min));
}

async function _humanPause(minMs, maxMs) {
  await new Promise((r) => setTimeout(r, _randomInt(minMs, maxMs)));
}

async function _humanType(page, selector, text) {
  for (const ch of text) {
    await page.type(selector, ch, { delay: _randomInt(45, 140) });
    if (Math.random() < 0.08) await _humanPause(120, 320);
  }
}

async function _capture(page, name) {
  const path = `/tmp/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  const body = await page.evaluate(() => document.body?.innerText?.substring(0, 400) || "");
  console.log(`[capture] ${name} url=${page.url()}`);
  console.log(`[capture] ${name} body: ${body.replace(/\n/g, " | ")}`);
}

async function _humanClick(page, selector) {
  const box = await page.$eval(selector, (el) => {
    const rect = el.getBoundingClientRect();
    return { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
  });
  const targetX = box.x + box.w * (0.3 + Math.random() * 0.4);
  const targetY = box.y + box.h * (0.3 + Math.random() * 0.4);
  await page.mouse.move(targetX, targetY, { steps: _randomInt(15, 35) });
  await _humanPause(40, 140);
  await page.mouse.down();
  await _humanPause(30, 90);
  await page.mouse.up();
}

async function _selectChallengeResponse(page) {
  // Find and click the Challenge/Response link, then wait for navigation
  const [response] = await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2", timeout: 15_000 }).catch(() => null),
    page.evaluate(() => {
      const links = [...document.querySelectorAll("a")];
      const target = links.find((a) =>
        a.textContent.includes("Challenge/Response")
      );
      if (target) target.click();
    }),
  ]);
  console.log("[login] navigated after Challenge/Response click");
  await new Promise((r) => setTimeout(r, 2000));
  await page.screenshot({ path: "/tmp/login_03_challenge_page.png", fullPage: true });
  console.log("[login] Challenge/Response page body:",
    await page.evaluate(() => document.body?.innerText?.substring(0, 200) || ""));
}

async function _extractChallengeCode(page) {
  const code = await page.evaluate(() => {
    const body = document.body?.innerText || "";
    const match = body.match(/Challenge:\s*([\d\s]+)/);
    if (match) return match[1].replace(/\s/g, "");
    const digits = body.match(/(\d{3}\s?\d{3})/);
    if (digits) return digits[1].replace(/\s/g, "");
    return null;
  });
  console.log("[login] Challenge code extracted:", code);
  return code;
}

async function _findField(page, selectors) {
  for (const sel of selectors) {
    const el = await page.$(sel);
    if (el) return sel;
  }
  throw new Error(`No field found: ${selectors.join(", ")}`);
}

module.exports = { startLogin, submit2FA, resendSms, destroySession };
