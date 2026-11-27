const express = require("express");
const { startLogin, submit2FA, resendSms, destroySession } = require("./login");

const app = express();
app.use(express.json());

const PORT = process.env.LOGIN_SERVER_PORT || 5056;
const GATEWAY_URL = `https://localhost:${process.env.GATEWAY_PORT || 5055}`;
const TWO_FA_TIMEOUT_MS = 600_000;

let currentSession = null;
let sessionTimer = null;
let currentChallengeCode = null;
let currentMethod = null;

function clearSession() {
  if (sessionTimer) clearTimeout(sessionTimer);
  sessionTimer = null;
  if (currentSession) destroySession(currentSession);
  currentSession = null;
  currentChallengeCode = null;
  currentMethod = null;
}

app.post("/auto-login", async (req, res) => {
  const { username, password, mode } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: "username and password required" });
  }

  if (currentSession) {
    return res.status(409).json({ error: "Login already in progress" });
  }

  try {
    const result = await startLogin(GATEWAY_URL, username, password, mode || "live");

    if (result.status === "2fa_required") {
      currentSession = result.session;
      currentChallengeCode = result.challenge_code || null;
      currentMethod = result.method || "unknown";

      sessionTimer = setTimeout(() => {
        console.log("[auto-login] 2FA timeout, closing browser");
        clearSession();
      }, TWO_FA_TIMEOUT_MS);

      return res.json({
        status: "2fa_required",
        method: currentMethod,
        challenge_code: currentChallengeCode,
      });
    }

    return res.json(result);
  } catch (err) {
    console.error("[auto-login] Error:", err.message);
    clearSession();
    return res.status(500).json({ status: "failed", error: err.message });
  }
});

app.post("/auto-login/2fa", async (req, res) => {
  const { code } = req.body;

  if (!code) {
    return res.status(400).json({ error: "code required" });
  }

  if (!currentSession) {
    return res.status(400).json({
      error: "No login session pending. Call POST /auto-login first.",
    });
  }

  try {
    if (sessionTimer) clearTimeout(sessionTimer);
    sessionTimer = null;

    const result = await submit2FA(currentSession, code);
    currentSession = null;
    return res.json(result);
  } catch (err) {
    console.error("[auto-login] 2FA error:", err.message);
    clearSession();
    return res.status(500).json({ status: "failed", error: err.message });
  }
});

app.post("/auto-login/resend-sms", async (_req, res) => {
  if (!currentSession) {
    return res.status(400).json({
      error: "No login session pending. Call POST /auto-login first.",
    });
  }
  if (currentMethod !== "sms") {
    return res.status(409).json({
      error: `Resend SMS is only available for SMS 2FA (current method: ${currentMethod})`,
    });
  }
  try {
    const result = await resendSms(currentSession);
    return res.json(result);
  } catch (err) {
    console.error("[auto-login] resend-sms error:", err.message);
    return res.status(500).json({ status: "failed", error: err.message });
  }
});

app.get("/auto-login/debug", async (_req, res) => {
  if (!currentSession) return res.json({ error: "no session" });
  const body = await currentSession.page.evaluate(() => document.body?.innerText || "");
  res.type("text/plain").send(body);
});

app.get("/auto-login/cookies", async (_req, res) => {
  if (!currentSession) return res.json({ error: "no session" });
  const cookies = await currentSession.page.cookies();
  res.json(cookies);
});

app.post("/auto-login/dom", async (req, res) => {
  if (!currentSession) return res.status(400).json({ error: "no session" });
  const { text } = req.body || {};
  if (!text) return res.status(400).json({ error: "text required" });
  const result = await currentSession.page.evaluate((needle) => {
    const lower = needle.toLowerCase();
    const candidates = [...document.querySelectorAll("a, button, span, label, p, div")];
    const visible = candidates.filter((el) => {
      if (el.offsetParent === null) return false;
      const style = window.getComputedStyle(el);
      return style.display !== "none" && style.visibility !== "hidden";
    });
    const exact = visible.find((el) => el.textContent.trim().toLowerCase() === lower);
    const tight = visible.find((el) => {
      const t = el.textContent.trim().toLowerCase();
      return t.includes(lower) && t.length < lower.length * 2 + 10;
    });
    const target = exact || tight;
    if (!target) return null;
    const path = [];
    let cur = target;
    for (let i = 0; i < 4 && cur; i++) {
      path.push({
        tag: cur.tagName,
        id: cur.id,
        className: cur.className,
        href: cur.getAttribute && cur.getAttribute("href"),
        role: cur.getAttribute && cur.getAttribute("role"),
        onclick: !!cur.onclick,
        outerHTMLPreview: cur.outerHTML?.slice(0, 200),
      });
      cur = cur.parentElement;
    }
    return { target_outerHTML: target.outerHTML.slice(0, 400), ancestors: path };
  }, text);
  res.json(result || { error: "not found" });
});

app.post("/auto-login/eval", async (req, res) => {
  if (!currentSession) return res.status(400).json({ error: "no session" });
  const { script } = req.body || {};
  if (!script) return res.status(400).json({ error: "script required" });
  try {
    const result = await currentSession.page.evaluate(script);
    res.json({ result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/auto-login/fingerprint", async (_req, res) => {
  if (!currentSession) return res.json({ error: "no session" });
  const fp = await currentSession.page.evaluate(() => ({
    webdriver: navigator.webdriver,
    userAgent: navigator.userAgent,
    languages: navigator.languages,
    plugins: [...navigator.plugins].map((p) => p.name),
    pluginCount: navigator.plugins.length,
    chromeRuntime: typeof window.chrome?.runtime,
    notificationPermission: typeof Notification !== "undefined" ? Notification.permission : null,
    webglVendor: (() => {
      try {
        const canvas = document.createElement("canvas");
        const gl = canvas.getContext("webgl");
        const ext = gl.getExtension("WEBGL_debug_renderer_info");
        return {
          vendor: gl.getParameter(ext.UNMASKED_VENDOR_WEBGL),
          renderer: gl.getParameter(ext.UNMASKED_RENDERER_WEBGL),
        };
      } catch (e) { return { error: e.message }; }
    })(),
    platform: navigator.platform,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory,
  }));
  res.json(fp);
});

app.post("/auto-login/click", async (req, res) => {
  if (!currentSession) return res.status(400).json({ error: "no session" });
  const { text } = req.body || {};
  if (!text) return res.status(400).json({ error: "text required" });
  const page = currentSession.page;
  const rect = await page.evaluate((needle) => {
    const lower = needle.toLowerCase();
    const candidates = [...document.querySelectorAll("a, button, span, label, p, div")];
    const visible = candidates.filter((el) => {
      if (el.offsetParent === null) return false;
      const style = window.getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    const exact = visible.find((el) => el.textContent.trim().toLowerCase() === lower);
    const tight = visible.find((el) => {
      const t = el.textContent.trim().toLowerCase();
      return t.includes(lower) && t.length < lower.length * 2 + 10;
    });
    const target = exact || tight;
    if (!target) return null;
    target.scrollIntoView({ block: "center" });
    const r = target.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, tag: target.tagName, txt: target.textContent.trim().slice(0, 80) };
  }, text);
  if (!rect) return res.json({ clicked: false, reason: "element not found" });
  await page.mouse.move(rect.x, rect.y, { steps: 20 });
  await new Promise((r) => setTimeout(r, 100));
  await page.mouse.down();
  await new Promise((r) => setTimeout(r, 60));
  await page.mouse.up();
  await new Promise((r) => setTimeout(r, 2000));
  const screenshotPath = `/tmp/click_${Date.now()}.png`;
  await page.screenshot({ path: screenshotPath, fullPage: true });
  const body = await page.evaluate(() => document.body?.innerText || "");
  res.json({ clicked: true, target: rect, screenshot: screenshotPath, body });
});

app.get("/auto-login/health", (_req, res) => {
  res.json({
    status: "ok",
    session_active: currentSession !== null,
  });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[auto-login] Server listening on port ${PORT}`);
  console.log(`[auto-login] Gateway URL: ${GATEWAY_URL}`);
  console.log(`[auto-login] 2FA timeout: ${TWO_FA_TIMEOUT_MS / 1000}s`);
});
