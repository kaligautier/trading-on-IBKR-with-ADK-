const http = require("node:http");

// Contract: https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run
http.createServer((req, res) => {
  res.setHeader("Content-Type", "application/json");
  const match = req.url.split("?")[0].match(
    /^\/v2\/projects\/test-project\/locations\/europe-west1\/jobs\/(accepted|denied|unavailable):run$/
  );
  if (req.method !== "POST" || !match) {
    res.writeHead(501);
    return res.end(JSON.stringify({error: {code: 501, message: "Unexpected call, including operation polling"}}));
  }
  if (Object.keys(req.body || {}).length) {
    res.writeHead(400);
    return res.end(JSON.stringify({error: {code: 400, message: "Expected the configured Job without overrides"}}));
  }
  if (match[1] !== "accepted") {
    const code = match[1] === "denied" ? 403 : 503;
    res.writeHead(code);
    return res.end(JSON.stringify({error: {code, message: "Private upstream details"}}));
  }
  res.end(JSON.stringify({
    name: "projects/test-project/locations/europe-west1/operations/submitted",
    done: false
  }));
}).listen(process.env.PORT);
