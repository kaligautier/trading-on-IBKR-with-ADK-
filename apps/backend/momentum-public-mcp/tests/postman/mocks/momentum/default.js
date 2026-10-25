// Read contract: apps/backend/momentum-api/openapi.json.
// Suggestions contract: recovered DeepCopy Momentum API. Synthetic local data.
const http = require("http");
http.createServer(async (req,res) => {
 const url = new URL(req.url,"http://localhost");
 const send = (status,body) => {res.writeHead(status,{"Content-Type":"application/json"});res.end(JSON.stringify(body));};
 if(req.headers["authorization"] !== "Bearer disposable-momentum-token") return send(401,{error:"invalid bearer"});
 const summary={"id": "11111111-1111-1111-1111-111111111111", "ticker": "AAPL", "analysis_date": "2026-10-23", "created_at": "2026-10-23T12:00:00Z", "llm_provider": "google", "next_analysis_date": null, "rating": "Buy"};
 const detail={"id": "11111111-1111-1111-1111-111111111111", "ticker": "AAPL", "analysis_date": "2026-10-23", "created_at": "2026-10-23T12:00:00Z", "llm_provider": "google", "next_analysis_date": null, "rating": "Buy", "deep_think_llm": "fixture", "quick_think_llm": "fixture", "next_analysis_desc": null, "technical_indicators": null, "fundamentals": null, "sentiment": null, "news": null, "research_plan": null, "trader_proposal": null, "portfolio_decision": null, "debate_arguments": [], "run_stats": null};
 const suggestion={"id": "22222222-2222-2222-2222-222222222222", "symbol": "MSFT", "reason": "MCP migration test", "status": "pending", "source": "mcp", "created_at": "2026-10-24T00:00:00Z", "reviewed_at": null, "review_reason": null};
 if(req.method==="POST" && url.pathname==="/suggestions") {
  if(!req.headers["x-momentum-signature"] || !req.headers["x-momentum-caller"]) return send(403,{});
  await pm.state.set("suggestions.record",{...suggestion,symbol:req.body.symbol,reason:req.body.reason});
  return send(202,await pm.state.get("suggestions.record"));
 }
 if(req.method==="GET" && url.pathname===`/suggestions/${suggestion.id}`) {
  const stored=await pm.state.get("suggestions.record");
  return stored ? send(200,stored) : send(404,{});
 }
 if (req.method !== "GET") return send(501,{});
 if (url.pathname === `/v1/analyses/${summary.id}`) return send(200,detail);
 if (["/v1/analyses","/v1/analyses/latest","/v1/recommendations"].includes(url.pathname)) {
   if ([...url.searchParams.keys()].some(k => !["ticker","rating","page_size","page_token"].includes(k))) return send(400,{});
   const size=Number(url.searchParams.get("page_size"));
   if(size<1 || size>100) return send(400,{});
   if(url.searchParams.get("ticker")==="FAIL") return send(503,{error:"fixture upstream unavailable"});
   if(url.searchParams.get("ticker")==="SLOW") return setTimeout(() => send(200,{items:[{...summary,ticker:"SLOW"}],next_page_token:""}),11000);
   return send(200,{items:[summary],next_page_token:""});
 }
 return send(501,{});
}).listen(process.env.PORT);
