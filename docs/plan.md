# Plan: four adapters → one DIAL Adapter

Migration plan. For the target architecture see [design.md](design.md).

## The problem

We ship four adapters, named after clouds:
[openai](https://github.com/epam/ai-dial-adapter-openai/),
[bedrock](https://github.com/epam/ai-dial-adapter-bedrock/),
[vertexai](https://github.com/epam/ai-dial-adapter-vertexai/),
[dial](https://github.com/epam/ai-dial-adapter-dial/).

The names stopped matching reality:

| You want to connect to | Adapter you need | Obvious? |
| ---------------------- | ---------------- | -------- |
| GPT on Azure OpenAI | openai | yes |
| Claude on AWS Bedrock | bedrock | yes |
| Gemini on Vertex AI | vertexai | yes |
| **OpenAI models on AWS Bedrock** | **openai** | no |
| **Claude on Vertex AI** | **vertexai** | no |
| **A self-hosted vLLM endpoint** | **openai** | no |
| **Any vendor speaking Chat Completions / Messages / Responses** | **openai** | no |

So the openai adapter is really two things: an Azure OpenAI adapter, and a thin auth
layer in front of anything OpenAI-compatible. Users cannot guess which image to deploy.
That is mental overhead we impose for no reason.

## Options

| # | Option | Verdict |
| - | ------ | ------- |
| 1 | Keep four adapters, fix the incongruences | Renaming does not remove the choice. Four of everything stays. |
| 2 | Split per vendor: azure, openai, anthropic, aws, gcp, fireworks, alibaba, self-hosted… | More images, more releases, same question asked more often. |
| 3 | **One universal image**, like [LiteLLM](https://github.com/BerriAI/litellm) | **Chosen.** One image, one config surface, one thing to deploy. |

> [!NOTE]
> LiteLLM proves the shape works: one container, 155 providers, every cloud auth flow.
> Its provider integrations are pure request/response transformations over one shared
> HTTP client — see [`ARCHITECTURE.md`](https://github.com/BerriAI/litellm/blob/main/ARCHITECTURE.md)
> and [`base_llm/chat/transformation.py`](https://github.com/BerriAI/litellm/blob/main/litellm/llms/base_llm/chat/transformation.py).

## Target

One image, and a first path segment that says what the request is for. Two shapes,
because **the adapter is not the vendor** — the incongruence above, in path form.

**Phase 4 — `/compat/{adapter}/…`.** One segment naming the codebase that answers,
fenced off as what it is: a compatibility surface that exists only while the four
adapters are still four.

```
/compat/adapter-openai/openai/deployments/{deployment_name}/*
/compat/adapter-vertexai/openai/deployments/{deployment_name}/*
/compat/adapter-bedrock/openai/deployments/{deployment_name}/*
/compat/adapter-dial/openai/deployments/{deployment_name}/*
/health
```

**Phase 5 — `/{vendor}/…`.** The segment names who hosts the model; the tail is the
[DIAL Core](https://dialx.ai/dial_api) API surface, unchanged:

```
/azure/openai/v1/chat/completions
/aws/anthropic/v1/messages
/gcp/openai/deployments/{deployment_name}/*
/openai-platform/openai/v1/responses
/anthropic-platform/anthropic/v1/messages
/fireworks/openai/v1/chat/completions
/alibaba/openai/v1/embeddings
/health
```

The vendor list is open-ended — `azure`, `aws`, `gcp`, `openai-platform`,
`anthropic-platform`, `fireworks`, `alibaba`, whatever comes next. The second segment
stays the API the client speaks (`openai` or `anthropic`), exactly as Core exposes it.

Why the vendor and not the adapter: a Core config author knows where the deployment
lives, not which of our repos grew the code. Today they have to know both — OpenAI
models on Bedrock are served by the *openai* adapter, Claude on Vertex AI by the
*vertexai* one.

Upstream endpoint, key and per-deployment settings stay in headers
(`X-UPSTREAM-ENDPOINT`, `X-UPSTREAM-KEY`, `X-UPSTREAM-EXTRA-DATA`) — where DIAL already
puts them today.

---

## Phase 1 — monorepo, still four images

No behaviour change. Nothing to re-deploy differently.

1. Move all four sources into this repo, as a copy at a recorded commit (CLAUDE.md).
2. CI builds **four** images from four Dockerfiles, under today's names.
3. Lockstep versioning: one version for the repo, all four images get it.
4. First version: **0.44.0** — the highest of the four lines (openai 0.43.2) plus a
   minor bump.
5. Accept empty releases: an untouched adapter still gets a new version.

**Done when:** `make lint && make test` are green and all four images publish from this
repo.

<details>
<summary>Why lockstep, and what an empty release costs</summary>

Per-adapter version lines need prefixed tags (`openai/0.44.0`), one release branch per
adapter, and a local replacement for
[`semantic_versioning`](https://github.com/epam/ai-dial-ci/tree/main/actions/semantic_versioning),
which anchors every tag lookup to a bare `X.Y.Z`. Phase 4 collapses to one image
anyway, so that work would be thrown away. The cost of lockstep is an image tag that
contains no changes — consumers bump a version for nothing. It is one line in a values
file.
</details>

## Phase 2 — remove the blockers

Both must be done before one process can serve everything.

**2a. Environment variables that collide.**

| Variable | Problem |
| -------- | ------- |
| `COMPATIBILITY_MAPPING` | maps Vertex AI names in one adapter, Bedrock names in another |
| `DEFAULT_REGION` | `us-central1` (GCP) in one, an AWS region in another |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ASSUME_ROLE_ARN` | read by both bedrock and openai; today they may name two different accounts |

Fix: move per-deployment values into `X-UPSTREAM-EXTRA-DATA` (the adapters already
parse credentials, region, project and assume-role from it), and prefix whatever must
stay in the environment. No silent fallback to the bare name.

**2b. One route table.** Serve every adapter from one FastAPI app under a prefix —
`/compat/adapter-openai`, `/compat/adapter-bedrock`, `/compat/adapter-vertexai`, `/compat/adapter-dial` — with
telemetry, logging and `/health` owned by the root app.

**Done when:** one process answers all four prefixes, and a deployment needs only the
credentials of the provider it actually uses.

<details>
<summary>The trap in mounting sub-apps</summary>

Starlette does not run the lifespan of a mounted app. Our adapters open HTTP clients,
boto clients and DIAL client pools there. Mounted naively, none of that is created or
closed. So the adapters' apps carry no lifespan of their own, and
`aidial_model_provider/app.py` enters each one's `lifespan` function explicitly;
`tests/unit_tests/model_adapter/test_lifespan.py` pins it.
</details>

## Phase 3 — good to have

Not blockers. Each is worth doing on its own.

- **One HTTP client.** Central timeouts, retries, pool limits, SSL and proxy config.
  LiteLLM runs every provider — including the `openai` SDK path — on a single
  `aiohttp` connector, and has one 29-line module that decides what a timeout means.
- **One internal package.** 32 near-duplicate module pairs exist across the four
  adapters today (`compatibility_mapping` 0.99 similar, `url.py` 0.96, `dial_api/*`
  0.92). Merge them one family per PR.

## Phase 4 — one image

1. One `pyproject.toml`, one lockfile, one Dockerfile.
2. Publish `epam/ai-dial-model-adapter`. Keep the four old images for one release
   cycle, then archive the old repos.
3. Core configs change to the new base URL plus the `/compat/{adapter}` prefix.

**Done when:** one image serves every model any of the four served, each under
`/compat/{adapter}`.

## Phase 5 — vendor routes

Dispatch on vendor + upstream API instead of on which of the four codebases owns the
model: `/azure/*`, `/aws/*`, `/gcp/*`, `/openai-platform/*`, `/fireworks/*`, …
`/compat/adapter-*` stays mounted as an alias for as long as Core configs still name it — one
rewrite rule, not a second migration.

Needs Phase 3's merge first: `/aws/openai/v1/chat/completions` (OpenAI models on
Bedrock) and `/aws/anthropic/v1/messages` (Claude on Bedrock) are two different
codebases today.

**Done when:** a deployment's path names the provider it talks to, and no path names
one of our repos.

## Phase 6 — an adapter SDK

Extract the contract a provider integration implements — transform request, transform
response, resolve auth headers — into a package, and build the adapter on it. Third
parties then add a vendor without forking us.

> [!TIP]
> LiteLLM's version of this contract is five methods, none of which does I/O, plus a CI
> gate ([`enforce_llms_folder_style.py`](https://github.com/BerriAI/litellm/blob/main/tests/code_coverage_tests/enforce_llms_folder_style.py))
> that keeps new providers on the pattern. 118 of their 135 provider directories import
> no vendor SDK at all.

---

## Image size

> [!NOTE]
> The 361.2 MB on [hub.docker.com/r/litellm/litellm](https://hub.docker.com/r/litellm/litellm)
> is **compressed** — the download, not the disk. Measured on the registry, their
> `linux/amd64` image is 383.5 MB compressed across 22 layers.

What is in LiteLLM's image, and what we would carry too:

| Layer | Size (compressed) | Us? |
| ----- | ----------------- | --- |
| `/app/.venv` — 193 Python packages | 202.8 MB | partly |
| `/opt/prisma` — Prisma CLI + Rust query engines | 93.7 MB | **no** |
| `apk` runtime: bash, openssl, nodejs, python, libsndfile | 70.2 MB | smaller (no node) |
| enterprise + proxy-extras source, admin UI | 7.7 MB | **no** |
| Wolfi base | 7.4 MB | ~ same |

Their venv by group (wheel bytes), against what our adapters need:

| Group | Wheels | Ours too? |
| ----- | ------ | --------- |
| Cost export and analytics — polars, numpy, redisvl, semantic-router | 63.8 MB | numpy only |
| Google — `google-*`, grpcio, protobuf | 20.3 MB | **yes** |
| AWS — botocore, boto3, awscrt, smithy | 19.9 MB | **yes** |
| Observability — otel, ddtrace, sentry, langfuse | 13.6 MB | otel only |
| Server runtime — granian, uvicorn, gunicorn, fastapi | 11.8 MB | **yes**, smaller |
| Tokenizers — tiktoken, tokenizers, huggingface-hub | 10.8 MB | tiktoken only |
| SAML SSO, database, everything else | 38.0 MB | mostly **no** |

All four vendor SDK families together are 43.6 MB of wheels — **12% of their image**.
Prisma plus Node plus CPython is 43%.

Our four adapters today, production closure only, installed on disk including `.pyc`:

```
openai   173 MB     vertexai 316 MB     bedrock 139 MB     dial 69 MB
union of all four: 356 MB
```

**Expected final image: ~400–450 MB on disk, ~100–140 MB compressed.** Roughly a third
of LiteLLM's, because we carry no Prisma, no Node, no admin UI and no analytics stack.

Two levers would take the dependencies from 356 MB to about 170 MB:

| Lever | Saves | Note |
| ----- | ----- | ---- |
| Multimodal embeddings off `vertexai.vision_models` onto `google-genai` | 149 MB | `google-cloud-aiplatform` is 149 MB and we import two names from it |
| OTLP exporter from gRPC to HTTP | 38 MB | `grpcio` is in all four adapters, pulled only by `aidial-sdk[telemetry]` |

<details>
<summary>Why LiteLLM ships the 149 MB anyway</summary>

`google-cloud-aiplatform` is an optional `litellm[google]` extra for library users, but
their Dockerfile installs `--extra proxy-runtime`, which contains it along with
`google-genai`, `anthropic[vertex]` and a pinned `grpcio`. Everyone running their image
gets it. What their call-site imports buy is the *option* to install without it, not a
smaller container.
</details>

## Third-party dependency conflicts

One image means one resolution. Two provider SDKs can demand incompatible versions of a
shared transitive dependency. LiteLLM hits this and handles it in
[`pyproject.toml`](https://raw.githubusercontent.com/BerriAI/litellm/refs/heads/litellm_internal_staging/pyproject.toml):

```toml
[tool.uv]
override-dependencies = [
    # a2a-sdk 1.x requires packaging>=24.0; lunary 1.4.x still caps at <24.0.
    "packaging>=24.0",
    "cryptography>=50.0.0,<51.0",
]
constraint-dependencies = [        # floors for transitive packages under a CVE
    "tornado>=6.5.8", "aiohttp>=3.14.2,<4.0", "setuptools>=83.0.0", …
]
exclude-newer = "3 days"           # a fresh release cannot land in a refresh
```

- [`override-dependencies`](https://docs.astral.sh/uv/reference/settings/#override-dependencies)
  forces a version when two direct dependencies disagree irreconcilably.
- [`constraint-dependencies`](https://docs.astral.sh/uv/reference/settings/#constraint-dependencies)
  raises a transitive floor without adding a dependency.
- Builds run `uv sync --frozen` against a committed lock, so **the build cannot break**
  from an upstream release. Only a deliberate lock refresh can.

We are on Poetry, which has no `override-dependencies`. The equivalents are
`[tool.poetry.dependencies]` entries that pin the shared transitive package directly.
Worth revisiting uv once the four dependency sets are merged.

> [!IMPORTANT]
> Alignment is a **prerequisite** of Phase 4, not a cleanup. The hard one is `openai`,
> pinned at 2.48.0 / 1.107.3 / 1.32.0 across three adapters. Do the bumps in the
> standalone repos during Phase 1, where a break is attributable to one adapter.

## Security

> [!NOTE]
> One repo is an argument *for* this plan, not against it. An advisory is fixed once,
> reviewed once, released once — instead of four times across four repos with four
> version bumps.

The real cost is that one image carries the union of every provider's CVEs: a
`google-cloud-*` advisory can hold up a release that only contains an openai fix. That
is the same trade LiteLLM makes, and it is why the two size levers above are worth
pulling — every package removed is a package that cannot be advised against.

## Where this repo stands

- Scaffold, single Poetry project, one Dockerfile, composition root, CI → committed.
- Phase 1 wants the **four-image** CI back. It is in this repo's history — lockstep
  version, matrix over the four adapters, today's image names:
  `git show 5ba1a94:.github/workflows/release.yml`.
- Nothing is imported yet. Phase 1 step 1 is the next action.
