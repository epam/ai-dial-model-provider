"""Telemetry is configured once, by the root app, for the whole process.

This needs a subprocess with OTEL_TRACES_EXPORTER set, because
`TelemetryConfig()` reads that at construction: with no OTEL_* variable every
field defaults to None, `init_telemetry` does nothing, and an adapter that
re-enabled telemetry would look identical to one that did not. In other words
the failure this guards against is invisible in a normal test run and only
appears in a deployment that exports traces -- five TracerProvider overrides,
five instrumentors, five OTLP log handlers on the root logger, and a
prometheus port bound five times.

`console` rather than `otlp` keeps TracingConfig non-None (so FastAPI really is
instrumented) while constructing no exporter, so nothing opens a connection.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# The probe must run from the repo root, so that `aidial_model_provider` is
# importable. Found by walking up to pyproject.toml rather than counting
# parents, which silently breaks the next time this file moves.
_REPO_ROOT = next(
    p for p in Path(__file__).parents if (p / "pyproject.toml").is_file()
)

PROBE = """
import json
from aidial_model_provider.app import (
    app, openai_app, vertexai_app, bedrock_app, dial_app,
)

def instrumented(a):
    return bool(getattr(a, "_is_instrumented_by_opentelemetry", False))

print(json.dumps({
    "root": instrumented(app),
    "openai": instrumented(openai_app),
    "vertexai": instrumented(vertexai_app),
    "bedrock": instrumented(bedrock_app),
    "dial": instrumented(dial_app),
}))
"""


def test_only_the_root_app_is_instrumented():
    env = {
        **os.environ,
        "OTEL_TRACES_EXPORTER": "console",
        "DIAL_URL": "http://localhost:8080",
        "PYDANTIC_V2": "1",
    }
    # S603: the command is this interpreter and a literal defined above.
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        env=env,
        cwd=_REPO_ROOT,
    )
    assert out.returncode == 0, out.stderr

    result = json.loads(out.stdout.strip().splitlines()[-1])

    assert result["root"], "the root app must own telemetry"
    for adapter in ("openai", "vertexai", "bedrock", "dial"):
        assert not result[adapter], (
            f"the {adapter} adapter configured telemetry of its own; "
            "it is mounted, so the root app has already done it"
        )
