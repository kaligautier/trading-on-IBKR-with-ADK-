# Market provider contract simulation

From `apps/backend/momentum-adk`, start (Postman CLI >= 1.73):

```sh
postman simulation run tests/postman/market.sim.yaml --port 4909 --output ndjson
```

In another terminal run `uv run python tests/postman/verify_alpha.py`.
Inspect the simulation request log, then stop it with Ctrl-C.
Fixtures follow the public Alpha Vantage contract. Owner mock discovery was
unavailable without Postman login. Yahoo SDK regressions run in the unit suite;
this simulation does not establish live Yahoo availability.
