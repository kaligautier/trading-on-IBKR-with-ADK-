// Synthetic fixtures from https://www.alphavantage.co/documentation/.
const http = require("http");
http.createServer((req, res) => {
  const u = new URL(req.url, "http://localhost");
  const q = u.searchParams;
  const send = (code, body) => {
    res.writeHead(code, {"Content-Type": "application/json"});
    res.end(JSON.stringify(body));
  };
  if (u.pathname !== "/query") return send(501, {});
  if (q.get("function") === "NEWS_SENTIMENT") {
    if (!q.get("time_to").endsWith("T2359")) return send(400, {error: "Incomplete calendar end date"});
    return send(200, {feed: [{title: "Evening headline", time_published: "20261020T230000"}]});
  }
  if (q.get("function") === "BALANCE_SHEET") return send(200, {annualReports: [{fiscalDateEnding: "2000-01-01"}, {fiscalDateEnding: "9999-01-01"}]});
  const columns = {
    SMA: "SMA", EMA: "EMA", MACD: "MACD,MACD_Signal,MACD_Hist",
    RSI: "RSI", BBANDS: "Real Middle Band,Real Upper Band,Real Lower Band", ATR: "ATR",
  }[q.get("function")];
  if (columns && q.get("datatype") === "csv") {
    res.writeHead(200, {"Content-Type": "text/csv"});
    const values = columns.split(",").map(() => "42").join(",");
    return res.end(`time,${columns}\n2026-10-24,${values}\n2026-10-23,${values}\n2026-10-21,${values}\n2026-10-20,${values}\n`);
  }
  return send(501, {});
}).listen(process.env.PORT);
