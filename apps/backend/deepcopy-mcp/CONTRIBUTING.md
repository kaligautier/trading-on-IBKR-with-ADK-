# Contributing

1. Install dependencies with `just install`.
2. Put business logic in `src/app/services/`, domain models in `models/`, and MCP
   adapters in `core_components/`. Each external API owns its `client/`, `config/`,
   and `dtos/request/response/` under `api/<name>/`. Manage clients in `lifespan.py`.
3. Test the service and its MCP contract with `Client(create_server(settings))`.
   Check results, errors, schemas, and annotations.
4. Run Ruff, ty, and pytest using the commands in the [README](README.md).

Keep FastMCP context and authorization in the MCP layer. Use explicit timeouts for
network I/O. Declare accurate tool annotations; they do not enforce permissions.
Tool arguments are logged by default, so disable argument logging for sensitive inputs.

Dependencies are locked in `uv.lock`. After changing `pyproject.toml`, run
`uv lock` and recheck the project. Do not commit credentials or downloaded pages.
