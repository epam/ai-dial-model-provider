<h1 align="center">
  DIAL Model Provider
</h1>
<p align="center">
  <p align="center">
  <a href="https://dialx.ai/">
    <img src="https://dialx.ai/logo/dialx_logo.svg" alt="About DIALX">
  </a>
</p>
<h4 align="center">
  <a href="https://discord.gg/ukzj9U9tEe">
    <img src="https://img.shields.io/static/v1?label=DIALX%20Community%20on&message=Discord&color=blue&logo=Discord&style=flat-square" alt="Discord">
  </a>
</h4>

- [Overview](#overview)
  - [Served paths](#served-paths)
  - [Configuration](#configuration)
  - [Development](#development)
    - [Development Environment](#development-environment)
    - [Setup](#setup)
    - [IDE configuration](#ide-configuration)
    - [Make on Windows](#make-on-windows)
    - [Run](#run)
    - [Lint](#lint)
    - [Test](#test)
    - [Git hooks](#git-hooks)

---

# Overview

LLM Adapters unify the APIs of respective LLMs to align with the Unified Protocol of DIAL Core. Multi-modality allows supporting non-textual communications such as image-to-text, text-to-image, file transfers and more.

This project serves four DIAL adapters from **one image and one process**, each mounted under its own path prefix. The adapters themselves are unchanged: their sources are vendored here from the upstream repositories, so the models they support and the [AI DIAL API](https://dialx.ai/dial_api) they implement are exactly the ones documented there.

## Served paths

| Path prefix | Adapter | Models |
| ----------- | ------- | ------ |
| `/compat/openai/…` | [ai-dial-adapter-openai](https://github.com/epam/ai-dial-adapter-openai) | Azure OpenAI, the OpenAI platform and any OpenAI-compatible upstream |
| `/compat/vertexai/…` | [ai-dial-adapter-vertexai](https://github.com/epam/ai-dial-adapter-vertexai) | Google Cloud Vertex AI |
| `/compat/bedrock/…` | [ai-dial-adapter-bedrock](https://github.com/epam/ai-dial-adapter-bedrock) | AWS Bedrock |
| `/compat/dial/…` | [ai-dial-adapter-dial](https://github.com/epam/ai-dial-adapter-dial) | another DIAL Core instance |
| `/health` | this process | liveness of the whole container |

The tail of each path is the adapter's own DIAL API surface, unchanged — only the prefix is new. A DIAL Core upstream endpoint that pointed at `http://adapter-bedrock:5000/openai/deployments/{id}/chat/completions` becomes `http://model-provider:5000/compat/bedrock/openai/deployments/{id}/chat/completions`.

The prefix names the **adapter**, not the cloud: OpenAI models hosted on AWS Bedrock are served by `/compat/openai`, and Claude arrives through both `/compat/vertexai` and `/compat/bedrock`.

## Configuration

Every adapter reads the same environment variables it reads upstream, in one shared process environment. **See the respective adapter's README for its variables, supported models and per-deployment settings** — the table above links to all four.

See [`.env.example`](.env.example) for the shape of a local configuration.

## Development

### Development Environment

This project requires [Python ≥3.11](https://www.python.org/downloads/) and [Poetry ≥2.1.1](https://python-poetry.org/) for dependency management.

### Setup

1. Install Poetry. See the official [installation guide](https://python-poetry.org/docs/#installation).

2. _(Optional)_ Specify a custom Poetry executable in `.env.dev`. This is useful if multiple versions are installed. By default, `poetry` is used.

   ```sh
   POETRY=path-to-poetry-exe
   ```

3. Install the project dependencies (including linting, formatting and test tools). The virtual environment is created in `.venv` by the `virtualenvs.in-project` setting:

   ```sh
   make install
   source .venv/bin/activate
   ```

4. Copy [`.env.example`](.env.example) to `.env` and fill in the provider credentials. `make serve` passes it to the server and `pytest` loads it by itself; `make lint` and `make test` do not need it.

### IDE configuration

The recommended IDE is [VS Code](https://code.visualstudio.com/).
Open the project in VS Code and install the recommended extensions.
VS Code is configured to use the [Ruff formatter](https://docs.astral.sh/ruff/formatter/).

Alternatively you can use [PyCharm](https://www.jetbrains.com/pycharm/) that has built-in [Ruff support](https://www.jetbrains.com/help/pycharm/lsp-tools.html#ruff).

### Make on Windows

As of now, Windows distributions do not include the make tool. To run make commands, the tool can be installed using
the following command (since [Windows 10](https://learn.microsoft.com/en-us/windows/package-manager/winget/)):

```sh
winget install GnuWin32.Make
```

For convenience, the tool folder can be added to the PATH environment variable as `C:\Program Files (x86)\GnuWin32\bin`.
The command definitions inside Makefile should be cross-platform to keep the development environment setup simple.

### Run

Run the development server locally:

```sh
make serve
```

Build the image and run the server from a Docker container:

```sh
make docker
```

### Lint

Don't forget to run the linting before committing:

```sh
make lint
```

To auto-fix formatting issues run:

```sh
make format
```

### Test

To run the unit tests locally — every adapter's suite in one pytest process:

```sh
make test
```

The integration tests call live providers and need credentials in `.env`. One arithmetic question per model, across all three live adapters:

```sh
make integration_tests_smoke
```

The full live suites:

```sh
make integration_tests
```

Both accept extra pytest arguments, e.g. `make integration_tests ARGS='-k bedrock -n 16'`.

### Git hooks

You may optionally install Git hooks that will automatically run the linting step on Git push. You only need to do it once for the given repository.

```sh
make install_git_hooks
```

> [!IMPORTANT]
> This command doesn't work if you have already installed Git hooks locally or globally.
