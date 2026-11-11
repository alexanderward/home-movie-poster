# Command reference

The Makefile is the public command interface. `ARGS="..."` passes additional arguments where noted.

| Command | Purpose |
| --- | --- |
| `make help` | Show the public command catalogue. |
| `make setup` | Install locked Python and client dependencies. |
| `make start` | Build and start the development stack. |
| `make stop` | Stop the stack without deleting volumes. |
| `make restart` | Rebuild and recreate the stack. |
| `make logs` | Follow bounded Docker logs. |
| `make compose` | Pass `ARGS` to Docker Compose. |
| `make compose-check` | Validate development and production Compose configurations. |
| `make migrate` | Apply Django migrations. |
| `make manage` | Run a Django command supplied in `ARGS`. |
| `make web` | Run the ASGI server locally with reload. |
| `make client` | Run Vite locally. |
| `make monitor` | Run discovery and playback monitoring natively. |
| `make library-sync` | Queue a full library synchronization. |
| `make client-build` | Type-check and build modern and legacy bundles. |
| `make client-contracts` | Generate TypeScript contracts from Pydantic. |
| `make lint` | Run Ruff, import-linter, ESLint, and command documentation checks. |
| `make python-types` | Run Pyright. |
| `make test` | Run fast Python and client tests. |
| `make test-ui` | Run Playwright browser journeys. |
| `make test-db` | Run PostgreSQL/Redis integration tests. |
