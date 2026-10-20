// Contract: BerriAI/litellm v1.103.4 team/key management endpoints.
// Only synthetic credentials and records; this mock makes no upstream calls.
const http = require("http");
const { createHash } = require("crypto");
const token = createHash("sha256").update("offline-only-agent").digest("hex");
http.createServer(async (req, res) => {
  const path = new URL(req.url, "http://localhost").pathname;
  const send = (status, body) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
  };
  if (req.headers.authorization !== "Bearer offline-only-master") return send(401, {});
  if (path === "/__reset") {
    await pm.state.set("management", {
      team: null, updates: 0, fail: false,
      info: { team_id: null, models: ["offline-model"], max_budget: 10,
        budget_duration: "30d", spend: 2.5, budget_reset_at: "initial-window",
        permissions: {}, model_max_budget: {} },
    });
    return send(200, {});
  }
  const state = await pm.state.get("management");
  if (path === "/__state") return send(200, state);
  if (path === "/__fail") {
    state.fail = true;
    await pm.state.set("management", state);
    return send(200, {});
  }
  if (state.fail) return send(503, { error: "PRIVATE_UPSTREAM_DETAILS" });
  const body = req.body || {};
  const query = new URL(req.url, "http://localhost").searchParams;
  if (path === "/team/info") return send(state.team ? 200 : 404, { team_info: state.team });
  if (path === "/team/new" && state.team) return send(409, {});
  if (path === "/team/new" || path === "/team/update") {
    state.team = body;
  } else if (path === "/key/info") {
    return send(query.get("key") === token ? 200 : 404, { info: state.info });
  } else if (path === "/key/update") {
    if (body.key !== token || !body.permissions || !body.model_max_budget) return send(400, {});
    state.info = { ...state.info, ...body };
    if (body.budget_duration) state.info.budget_reset_at = "daily-window";
    state.updates++;
  } else {
    return send(501, { error: "Endpoint outside this contract" });
  }
  await pm.state.set("management", state);
  send(200, state);
}).listen(process.env.PORT);
