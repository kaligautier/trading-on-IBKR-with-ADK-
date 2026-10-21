// Contract: pinned LiteLLM management API, exercised by the real TF provider.
// Synthetic credentials only; no upstream calls.
const http = require("http");
const { createHash } = require("crypto");
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const path = url.pathname;
  const send = (status, body) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
  };
  if (req.headers.authorization !== "Bearer offline-only-master" && req.headers["x-api-key"] !== "offline-only-master") return send(401, {});
  if (path === "/__reset") {
    await pm.state.set("management", { team: null, keys: {}, updates: 0, fail: false });
    return send(200, {});
  }
  const state = await pm.state.get("management");
  if (path === "/__state") return send(200, state);
  if (path === "/__fail") {
    state.fail = true;
    await pm.state.set("management", state);
    return send(200, {});
  }
  if (state.fail) return send(503, { error: "upstream unavailable" });
  const body = req.body || {};
  let result;
  if (path === "/team/info") return send(state.team ? 200 : 404, { team_info: state.team });
  if (path === "/team/new" && state.team) return send(409, {});
  if (path === "/team/new" || path === "/team/update") {
    state.team = { ...state.team, ...body };
    result = state.team;
  } else if (path === "/key/info") {
    const info = state.keys[url.searchParams.get("key")];
    return send(info ? 200 : 404, { info });
  } else if (path === "/key/generate") {
    const token = createHash("sha256").update(body.key).digest("hex");
    state.keys[token] = { ...body, key: undefined, token, key_type: "default", spend: 0,
      permissions: {}, model_max_budget: {}, budget_reset_at: "2026-10-21T00:00:00Z" };
    result = { ...state.keys[token], token_id: token, key: body.key };
  } else if (path === "/key/update") {
    if (!state.keys[body.key]) return send(404, {});
    state.keys[body.key] = { ...state.keys[body.key], ...body, key: undefined };
    state.updates++;
    result = state.keys[body.key];
  } else return send(501, { error: "Endpoint outside this contract" });
  await pm.state.set("management", state);
  send(200, result);
}).listen(process.env.PORT);
