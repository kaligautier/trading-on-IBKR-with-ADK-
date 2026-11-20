# Market provider contract mock

From `apps/backend/momentum-adk`, start the synthetic Alpha Vantage server (Node >= 18):

```sh
PORT=4909 node tests/mocks/alpha/server.js
```

In another terminal run `uv run python tests/verify_alpha.py`, then stop the
server with Ctrl-C. Fixtures follow the public Alpha Vantage contract. Yahoo SDK
regressions run in the unit suite; this mock does not establish live Yahoo
availability.
