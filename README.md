# AI DIAL Model Adapter

One image, `epam/ai-dial-model-adapter`, serving every DIAL model adapter under its own
path prefix:

| Path                                                        | Package                   | Replaces repo                   |
| ----------------------------------------------------------- | ------------------------- | ------------------------------- |
| `/compat/openai/openai/deployments/{id}/chat/completions`   | `aidial_model_provider.openai`   | `epam/ai-dial-adapter-openai`   |
| `/compat/vertexai/openai/deployments/{id}/chat/completions` | `aidial_model_provider.vertexai` | `epam/ai-dial-adapter-vertexai` |
| `/compat/bedrock/openai/deployments/{id}/chat/completions`  | `aidial_model_provider.bedrock`  | `epam/ai-dial-adapter-bedrock`  |
| `/compat/dial/openai/deployments/{id}/chat/completions`     | `aidial_model_provider.dial`     | `epam/ai-dial-adapter-dial`     |
| `/health`                                                    | the process               | —                               |

The `openai/deployments/…` tail is the DIAL API path each adapter already serves; the
mount point names the adapter. DIAL Core upstream endpoints gain those segments.

`/compat` says what these paths are: the adapter is not the vendor — the openai adapter
also serves the OpenAI platform, Fireworks and any OpenAI-compatible endpoint.
Vendor-named routes (`/azure`, `/aws`, `/gcp`, `/openai-platform`, …) come later and
keep `/compat/*` as an alias — see [docs/plan.md](docs/plan.md), Target.

See [docs/design.md](docs/design.md) for the layout and the serving model, and
[docs/plan.md](docs/plan.md) for the staged migration from the four repos.

## Layout

```
aidial_model_provider/   composition root: builds the app, mounts the adapters
  app.py                 the app itself
  utils/                 code shared by the adapters
  <name>/                the four adapters, copied in (see CLAUDE.md)
tests/unit_tests/<name>/        per-adapter unit tests, plus model_adapter/
tests/integration_tests/<name>/ per-adapter live-provider tests
tests/{fixtures,utils,assets}/  shared by an adapter's two suites
pyproject.toml           one project, one lockfile — one process, one resolution
Dockerfile               one image
Makefile                 make lint / make test — the contract ai-dial-ci calls
```

## Usage

```sh
make install               # dependencies
make lint                  # ruff + pyright
make test                  # pytest (ARGS=... is passed through)
make serve                 # uvicorn aidial_model_provider.app:app
make docker                # build and run the image
```

Every adapter is always mounted; there is no enablement switch. Which adapters are
reachable is DIAL Core's routing decision, and which credentials a deployment uses
arrives per request in the `x-upstream-extra-data` / `x-upstream-key` headers — see
[docs/design.md](docs/design.md) §4.

`LOG_LEVEL` is process-wide: the four adapters log through one logger, so `DEBUG` turns it on for all of them -- and DEBUG prints prompts.
