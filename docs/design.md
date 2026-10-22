# Monorepo design

One repository, **one image**, one process: `epam/ai-dial-model-adapter` serves all
four adapters, each mounted under its own path prefix.

This describes the target. For how we get there in stages, see [plan.md](plan.md).

## 1. What moves in, what stays out

| Repo                          | Verdict          | Why |
| ----------------------------- | ---------------- | --- |
| `ai-dial-adapter-openai`      | **in**, phase 1  | mounted at `/compat/openai` |
| `ai-dial-adapter-vertexai`    | **in**, phase 1  | mounted at `/compat/vertexai` |
| `ai-dial-adapter-bedrock`     | **in**, phase 1  | mounted at `/compat/bedrock` |
| `ai-dial-adapter-dial`        | **in**, phase 1  | mounted at `/compat/dial` |
| `ai-dial-adapter-anthropic`   | **in**, phase 2  | consumed *only* by the three adapters above. Every bump is a 4-PR round trip today |
| `ai-dial-sdk`                 | **out**          | 19 dependents across DIAL (rag, assistant, quickapps, interceptors…), public PyPI contract, own cadence |
| `ai-dial-client-python`       | **out**          | public PyPI client, also used by quickapps-backend |
| `ai-dial-interceptors-sdk`    | **out**          | different product (interceptors, not model adapters); repo name would lie |

Rule of thumb: **a package with consumers outside this repo stays out.** A monorepo
removes the release round-trip between its members and nothing else; for `aidial-sdk`
that round-trip is a feature — it is a versioned contract for other teams.

## 2. Why this is worth doing (measured, not assumed)

Copies of the same module, drifted, across the four adapters today:

```
0.99  vertexai/bedrock  utils/compatibility_mapping.py   (122/118 loc)
0.99  vertexai/bedrock  utils/adapter_deployment(s).py   (192/196 loc)
0.96  openai/vertexai   utils/url.py                     (120/120 loc)
0.95  vertexai/bedrock  anthropic_passthrough.py         ( 50/ 51 loc)
0.92  openai/vertexai   dial_api/storage.py, resource.py (315/355 loc)
0.91  openai/*          dial_api/embedding_inputs.py     ( 80/106 loc)
0.89  openai/*/dial     utils/log_config.py              ( 33 loc x4)
0.88  vertexai/bedrock  upstream_config.py               (181/188 loc)
…32 near-duplicate module pairs in total
```

The drift is the point, not the duplication: `utils/pydantic.py` is the same 9 lines in
openai and bedrock except the class is called `ExtraAllowedModel` in one and
`ExtraAllowModel` in the other. A fix to `dial_api/storage.py` has to be written,
reviewed and released four times.

Running them in **one process** turns some of that debt into outright bugs: four
`configure_loggers()` implementations configuring the same root logger, four telemetry
initialisations, four `/health` routes. Those are not optional cleanups any more — §4.

Costs, stated honestly: one image means one dependency resolution (§5), one release
train (§6), no runtime isolation between providers (§4), and 356 MB of dependencies in
every container whether it serves one provider or four (§7). 27k LOC of source and 27k
LOC of tests land in one working copy.

## 3. Layout

```
aidial_model_provider/    composition root: builds the app, mounts the adapters
  app.py                  the app itself
  utils/                  code shared by the adapters (logging today)
  openai/                 the four adapters, copied in from upstream
  vertexai/               (CLAUDE.md records the commits and the sync procedure)
  bedrock/
  dial/
tests/unit_tests/{openai,vertexai,bedrock,dial,model_adapter}/
tests/integration_tests/{openai,vertexai,bedrock}/
tests/{fixtures,utils,assets}/   shared by an adapter's two suites
pyproject.toml            one project, one lockfile
Dockerfile                one image
Makefile                  make lint / make test — the contract ai-dial-ci calls
scripts/                  docker entrypoints
```

One image serving one process means one Python distribution, so there are no
sub-projects, no path dependencies and no per-package lockfiles: those exist to keep
independently deployable things apart, and nothing here is independently deployable any
more.

**Python package names do change.** `aidial_adapter_openai` became
`aidial_model_provider.openai` when the sources moved into the package they are
served from; the rewrite is mechanical and CLAUDE.md records it as a step every
upstream sync repeats.

## 4. Serving model

`aidial_model_provider/app.py` is the whole composition root:

```
/health                                                    -> the process
/compat/openai/openai/deployments/{id}/chat/completions    -> aidial_model_provider.openai
/compat/vertexai/openai/deployments/{id}/chat/completions  -> aidial_model_provider.vertexai
/compat/bedrock/openai/deployments/{id}/chat/completions   -> aidial_model_provider.bedrock
/compat/dial/openai/deployments/{id}/chat/completions      -> aidial_model_provider.dial
```

The `openai/deployments/…` tail is the DIAL API path the adapters already serve; only
the leading segments are new. Every DIAL Core upstream endpoint pointing at these
services has to gain them — that is the migration's most visible edit, and it is
mechanical.

The mount point names the **adapter**, not the vendor: the openai adapter serves Azure,
the OpenAI platform, Fireworks and anything OpenAI-compatible, and Claude arrives
through both vertexai and bedrock. `/compat` marks that as the transitional surface it
is; vendor-named routes (`/azure`, `/aws`, `/gcp`, `/openai-platform`,
`/anthropic-platform`, …) are [plan.md](plan.md) Phase 5, and keep `/compat/*` mounted
as an alias.

Served as `uvicorn aidial_model_provider.app:app`. There is no factory: `app` is
built at module level and the four adapters are plain imports, so what is mounted is
visible to the reader and to the type checker. Importing the module therefore imports
all four provider SDKs — the accepted price of having nothing resolved from a string.

### What has to be exactly once per process

| Concern     | Today (×4)                              | Here |
| ----------- | --------------------------------------- | ---- |
| telemetry   | `init_telemetry(app, TelemetryConfig())`| root app only; the adapters' apps are built with it off |
| logging     | four `configure_loggers()`              | one `aidial_model_provider.utils.log_config`; the adapters' own are deleted and every module logs through its `logger` |
| `/health`   | one per adapter (`add_healthcheck=True`, or a route) | root app only; the container HEALTHCHECK keeps hitting `/health` |
| lifespan    | one per adapter                         | root lifespan enters each adapter's — see below |

**Starlette does not run the lifespan of a mounted app.** The adapters open HTTP
clients, Anthropic clients, boto clients and DIAL client pools there and close them on
the way out; mounted naively, nothing would ever be initialised or closed. So the
adapters' apps carry no lifespan of their own — leaving one attached would only make
it look like it runs — and the root `lifespan` enters each adapter's `lifespan`
function by hand. `tests/unit_tests/model_adapter/test_lifespan.py` pins that: it is the one
thing here that would break silently.

**Telemetry is the root app's, once.** Each adapter used to configure its own at
import — openai through `create_app(init_telemetry=True)`, vertexai and bedrock through
`DIALApp(telemetry_config=…)`, dial through a bare `init_telemetry(app, …)` — so one
process did it five times. That is invisible in development, because `TelemetryConfig()`
is a no-op unless an `OTEL_*_EXPORTER` variable is set, and harmful in production once
one is: five `TracerProvider` overrides, five instrumentors, five OTLP handlers on the
root logger (measured: 5 before, 1 after) and a Prometheus port bound five times.

The adapters' module-level apps are now built with telemetry off and
`aidial_model_provider/app.py` is the only caller. Mounting makes this correct as well
as tidy: a mounted sub-app is reached *through* the root's middleware stack, so the
root's FastAPI instrumentation already spans those requests. Leaving `telemetry_config`
unset on `DIALApp` also leaves its per-request `reset_otel_context` disabled, which is
what keeps the root's request span current inside the adapter instead of detached.
`tests/unit_tests/model_adapter/test_telemetry.py` pins it, in a subprocess with
`OTEL_TRACES_EXPORTER` set, since nothing else would notice.

### Which adapters are enabled: none of this process's business

An earlier draft had an `ENABLED_ADAPTERS=openai,bedrock` switch. It is gone: both
reasons for it turned out to be false, and it is not how anyone else solves this.

**LiteLLM** serves every provider from one container and has no such flag. Its
`config.yaml` lists deployments, and the provider is a prefix on the model name:

```yaml
model_list:
  - model_name: bedrock-claude-sonnet-4
    litellm_params:
      model: bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0
      aws_region_name: us-east-1          # and aws_access_key_id, aws_role_name, …
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY  # env is referenced, never implicit
```

Which providers are "enabled" is *derived* from that list, never declared. Credentials
are per deployment, so two entries can reach two different AWS accounts in one process
(`credential_list` + `CredentialAccessor` let them be named and reused), and where an
environment variable is used it is named explicitly as `os.environ/FOO` rather than
read behind the caller's back. Provider code is imported at the call site, not at boot
— `litellm/llms/vertex_ai/vertex_llm_base.py` imports `google.auth` inside the methods
that need it — so a container that never serves Vertex AI never touches it.

**DIAL already has the same mechanism**, and it sits in a better place: DIAL Core's
deployment config *is* the `model_list`, and it travels per request in the
`x-upstream-extra-data` and `x-upstream-key` headers.
`bedrock/upstream_config.py` reads region and either
`aws_access_key_id`/`aws_secret_access_key`/`aws_session_token` or an
`aws_assume_role_arn` (assumed per request, with STS session tags) out of that header;
the vertexai adapter does the same for GCP project and region, and for Azure Foundry
endpoints. The process environment only supplies *defaults* for those fields.

So neither reason for the flag survives:

- *"vertexai would need GCP credentials to start."* It would not. `init_vertex_ai()`
  logs a warning and returns when `GCP_PROJECT_ID`/`DEFAULT_REGION` are unset, and the
  real project and region arrive per request. Bedrock builds its boto clients per
  request too, and the openai adapter takes Azure credentials from headers. The only
  hard boot-time requirement among the four is the dial adapter's `DIAL_URL`, which
  every deployment sets anyway.
- *"it is the way back to per-provider isolation."* Routing already does that: run the
  image four times and point each DIAL Core deployment at the instance you want. An
  unused mount is a few rows in a route table, not a running cost.

**Configure credentials per deployment in DIAL Core, not per process.** Same answer as
LiteLLM, already implemented in the adapters, and it dissolves most of the environment
collisions below.

### Environment variables collide

The four adapters were configured independently, and their names overlap. Measured
across the four `.env.example` files and every `getenv` call:

| Variable | Conflict |
| -------- | -------- |
| `COMPATIBILITY_MAPPING` | vertexai maps *Vertex AI* deployment names, bedrock maps *Bedrock* ones. Same name, different meaning — **must be prefixed** |
| `DEFAULT_REGION` | `us-central1` (a GCP region) for vertexai; an AWS region for bedrock — **must be prefixed** |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_ASSUME_ROLE_ARN` | read by both bedrock and openai (Bedrock-hosted Anthropic). Today they can name two different AWS accounts; in one process they cannot |
| `ANTHROPIC_MAX_RETRY_ATTEMPTS`, `ACCESS_TOKEN_EXPIRATION_WINDOW`, `AZURE_OPEN_AI_SCOPE`, `CLAUDE_DEFAULT_MAX_TOKENS` | shared knobs that now tune two or three upstreams at once |
| `LOG_LEVEL`, `WEB_CONCURRENCY`, `DIAL_URL`, `PYDANTIC_V2` | genuinely process-wide; fine as they are |

Most of that list evaporates once credentials and regions come per deployment from
DIAL Core rather than from the process environment (above): the `AWS_*` variables and
`DEFAULT_REGION` are only defaults for the `x-upstream-extra-data` header, and a merged
deployment should stop relying on them. What stays genuinely process-wide and ambiguous
is `COMPATIBILITY_MAPPING` — a deployment-name mapping, not a credential — so **prefix
what still collides** (`VERTEXAI_COMPATIBILITY_MAPPING`,
`BEDROCK_COMPATIBILITY_MAPPING`) with no fallback to the bare name: a silent fallback
between two different meanings is worse than a startup failure.

`LOG_LEVEL` keeps working, but only process-wide: the four adapters share the single
`aidial_model_provider` logger, so `DEBUG` dumps the prompts of all four and `%(name)s`
no longer says which one emitted a line. A per-adapter level would need per-adapter
loggers back; the trade was made for one logging configuration instead of four.

### What one process costs

1. **No isolation.** One event loop: a saturated Vertex AI upstream, a CPU-bound
   tokenizer or a memory spike affects requests to every provider. Four deployments do
   not have that coupling.
2. **No independent scaling.** One Deployment, one HPA, one `WEB_CONCURRENCY` — and
   every uvicorn worker holds all four provider stacks in memory, not just the one it
   serves.
3. **Blast radius.** A bad release, or a failing readiness probe, takes out access to
   every model at once instead of one provider's.
4. **Telemetry route labels.** OpenTelemetry instruments the root app, and the route it
   records for a mounted app is the inner path — so vertexai and bedrock requests both
   report `http.route = /openai/deployments/{deployment_id}/chat/completions`. Their
   metrics and spans merge unless the prefix is added back by a small middleware.

1–3 stay recoverable without a rewrite: deploy the same image four times and let DIAL
Core route each deployment to its own instance. That is the four-service topology
again, with one artifact behind it and no switch in the image.

## 5. Dependencies: one project, one lockfile

One interpreter means one resolved version of every package, so reconciliation is no
longer a nice-to-have — it is a **prerequisite of the merge**. The 16 divergences that
exist today:

```
openai         2.48.0 / 1.107.3 / 1.32.0      <- the only hard one
pydantic       2.10.4 / 2.11.2 / 2.9.0
aidial-sdk     0.39.0 / 0.38.0
fastapi        0.135.1 / 0.136.3
azure-identity 1.16.1 / 1.25.1
boto3          1.43.56 / 1.43.74
numpy          2.3.3 / 2.0.0
httpx          0.27.0 / 0.28.1
uvicorn        0.23.0 / 0.22.0 / 0.23.2
requires-python  >=3.11,<3.13 / <3.14 / <4    -> the intersection, >=3.11,<3.13
aidial-client, asgi-lifespan, python-dotenv, pytest-timeout, respx, pyright
                                              <- same version, different spec syntax
```

Everything except `openai` is a version bump. `openai` is real work: the openai adapter
is already on 2.48, the vertexai adapter is on 1.107 and the dial adapter on 1.32 with
`AsyncAzureOpenAI`, so both need the 1.x → 2.x migration before they can share a
process. The openai adapter is the reference for how that was done.

Do this as a series of PRs **in the standalone repos, before importing them** — a
dependency bump that breaks one adapter is much easier to read than one that breaks a
merge.

## 6. Versioning, releases and CI

One image, one version, one release line. `epam/ai-dial-model-adapter:X.Y.Z`, tags
`X.Y.Z`, release branches `release-X.Y` — exactly the DIAL flow every other repo uses,
which means **the shared pipelines are reusable unchanged**:

```yaml
uses: epam/ai-dial-ci/.github/workflows/python_docker_release.yml@4.10.0
```

`IMAGE_NAME` defaults to `github.repository`, the Dockerfile and `pyproject.toml` are
at the root, and `make lint` / `make test` are the only entry points the shared
workflow calls. Nothing about the monorepo needs custom CI. (This is the one place
where the single image is a strict simplification: with four images, version stamping,
image naming and tagging all had to be reimplemented locally.)

The first version is **0.44.0**: the highest of the four lines (openai 0.43.2) plus a
minor bump — see [plan.md](plan.md), Phase 1. Record the mapping from the four old
lines in its release notes.

**The four old image names stop being published.** Every Helm values file, DIAL Core
config and deployment manifest that names `epam/ai-dial-adapter-openai` (and friends)
changes to `epam/ai-dial-model-adapter` plus a path prefix (§4). The four GitLab deploy
projects that `deploy-development.yml` triggers collapse into one. Keep publishing the
old images from the archived repos for one release cycle so consumers can move on their
own schedule.

## 7. Docker

One Dockerfile at the root, `python:3.11-alpine3.20` (the vertexai pin, the most
conservative of the four), with `geos-dev` for the vertexai build and the openai
adapter's tiktoken pre-caching. All four Dockerfiles were already the same otherwise.

Measured `site-packages` of the **production** closure only (`poetry show --only
main`), counting the `.pyc` files pip generates on install, deduplicated across
adapters:

```
                prod    with dev/test          union of the four:  356 MB
openai       173 MB           293 MB
vertexai     316 MB           386 MB
bedrock      139 MB           260 MB
dial          69 MB           135 MB
```

So one image is ~13% larger than today's vertexai image, and the cost lands on the
small adapters: the dial adapter goes from 69 MB of dependencies to 356 MB, and its
Trivy report becomes the union of every provider SDK's CVEs — a `google-cloud-*`
advisory now blocks the release that carries an openai fix.

Where the 356 MB actually goes, and the two levers worth pulling:

| Size | Package | Who needs it |
| ---- | ------- | ------------ |
| 149 MB | `google-cloud-aiplatform` | vertexai — but 137 MB of that is the generated `aiplatform_v1` + `aiplatform_v1beta1` proto stubs, and the adapter imports exactly `vertexai.init` and `vertexai.vision_models.MultiModalEmbeddingModel`. The Gemini path already runs on `google-genai` (6 MB) |
| 38 MB | `grpcio` | nobody, directly. It arrives via `aidial-sdk[telemetry]` → `opentelemetry-exporter-otlp-proto-grpc` in all four adapters — 55% of the dial adapter's entire footprint — and additionally via `google-api-core` in vertexai |
| 22 MB | `numpy` | openai, vertexai, bedrock — embeddings |
| 22 MB | `botocore` | bedrock, and openai for the Bedrock-hosted Anthropic passthrough. Mostly service-definition JSON |
| 15 MB | `pillow` | image attachments |
| 13 MB | `cryptography` | `azure-identity` → `msal` |
| 82 MB | 56 dists common to all four | of which grpcio is 38; the real shared base is ~44 MB |

LiteLLM shows that the *architecture* allows this, though its own image does not take
the option. Its library proxies every one of these providers on core dependencies of
`openai`, `httpx`, `aiohttp`, `tiktoken`, `tokenizers`, `boto3` and `pydantic` — no
`anthropic`, no `mistralai`, no `google-genai` — reaching providers over their REST
APIs with a transformation layer instead of a vendor SDK each, and importing what it
does need at the call site (`litellm/llms/vertex_ai/vertex_llm_base.py` wraps every
`google.auth` / `google.oauth2` import in a `try`, raising a "pip install
'litellm[google]'" hint if absent). Its *published image* installs
`--extra proxy --extra proxy-runtime --extra extra_proxy …`, and `proxy-runtime`
carries `google-cloud-aiplatform`, `google-genai`, `anthropic[vertex]` and a pinned
`grpcio`, so `ghcr.io/berriai/litellm` ships the same heavy SDKs we would. What the
call-site imports buy is the choice: the same codebase installs with or without them.

For scale: installing exactly what LiteLLM's Dockerfile installs (minus the
`semantic-router` and `saml` extras) gives **854 MB** of Python dependencies —
`google-cloud-aiplatform` 169 MB, `polars` 160 MB via `redisvl`, `litellm` itself
110 MB with its bundled admin UI, `grpcio` 39 MB, `ddtrace` 30 MB — and the published
`ghcr.io/berriai/litellm` amd64 image is 379 MB compressed on top of a Prisma engine
layer of 94 MB. One container carrying every provider is the norm, and at 356 MB ours
would be the light one.

Moving multimodal embeddings off `vertexai.vision_models` onto `google-genai` removes
149 MB and leaves OTLP as grpcio's only consumer; switching the SDK's telemetry extra
to `opentelemetry-exporter-otlp-proto-http` then removes another 38 MB. Together the
merged image would carry ~170 MB of dependencies — less than the openai adapter ships
today, for all four adapters. Neither change is required by the merge, and neither is
this repo's to make alone (the second is an `aidial-sdk` decision), but the single
image is what makes them worth doing once instead of four times.

## 8. Migration plan

1. **Align the dependencies** in the standalone repos (§5), `openai` 1.x → 2.x first.
2. **Add `create_app(init_telemetry=…)`** to the vertexai, bedrock and dial adapters
   (§4), still in their own repos, still shipping their own images. Nothing about this
   step is monorepo-specific and it can be reviewed provider by provider.
3. **Scaffold** (this commit): composition root, single project, one Dockerfile, CI.
4. **Copy the sources in** — *done*, see CLAUDE.md for the commits. History was
   not rewritten with `git-filter-repo` in the end: the adapters were taken as a
   plain copy of each upstream tree at a recorded commit, which is what makes the
   sync procedure in CLAUDE.md a two-directory `git archive | tar -x` rather than
   a merge. The cost is that `git log --follow` and `git blame` stop at the copy.
5. **Wire up** — *done*: the adapter packages became `aidial_model_provider/<name>`
   and their suites split into `tests/{unit_tests,integration_tests}/<name>`, with imports rewritten to match; the four dependency sets, pytest `addopts`, `filterwarnings` and `env`
   blocks merged into the root `pyproject.toml`; the per-adapter `noxfile.py`,
   `.pre-commit-config.yaml`, `Dockerfile`, `LICENSE`, `SECURITY.md`, `.github/`
   and `[tool.ruff]` dropped. `make lint && make test` are green. Still to do:
   delete each adapter's `utils/log_config.py` in favour of the common one, and
   carry over `.ort.yml`, `trivy.yaml` and `CONTRIBUTING.md`.
6. **Prefix the colliding env vars** (§4) and write the new `.env.example`.
7. **Release 1.0.0** and verify: all four adapters answer under their prefixes, one
   `/health`, telemetry flowing, and a Helm deployment that comes up with only one
   provider's credentials set.
8. **Freeze the old repos**: archive with a README pointing here, after one release has
   been served from the monorepo. Keep publishing the old images for one cycle.
9. **De-duplicate** into `aidial_model_provider.utils`, one module family per PR,
   highest-similarity first (`compatibility_mapping`, `adapter_deployments`,
   `upstream_config`, `dial_api/*`, `utils/*`). This is where the payoff arrives; the
   steps above only make it possible.
10. **Phase 2**: import `ai-dial-adapter-anthropic` as another package.

Steps 1–2 are useful on their own and reversible; step 4 onwards is the commitment.

## 9. Decisions for the team

1. Is losing per-provider isolation and independent scaling (§4) acceptable, or should
   the image be deployed four times from the start, with DIAL Core routing each
   deployment to its own instance? Only the Helm chart and Core config differ.
2. Mount the openai adapter at `/` instead of `/compat/openai`, so that the most widely
   deployed adapter's existing DIAL Core endpoints keep working? Cheap, but it makes
   the routing rule "one prefix per adapter, except one", and `/` is where the
   vendor-named routes go.
3. Prefix only the colliding env vars, or namespace all adapter-specific variables for
   consistency (`OPENAI_*`, `VERTEXAI_*`, …)? The first is a smaller migration, the
   second is easier to reason about.
4. `aidial-adapter-anthropic`: keep publishing it to PyPI from here, or demote it to an
   internal package? (§1)
