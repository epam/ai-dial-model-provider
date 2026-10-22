"""Logging is configured once, by the root app, for the whole process.

Two things can break it, and neither shows up as an error:

- A sync restores an adapter's own `utils/log_config.py`. Its modules then log
  through a logger of their own -- `bedrock`, `vertex-ai`,
  `aidial_model_provider.openai` -- which the root's LOG_LEVEL never reaches,
  so `LOG_LEVEL=DEBUG` silently stops working for that adapter.
- Something caches a level at import. `configure_loggers()` runs in
  `aidial_model_provider/app.py` *after* the four adapters are imported, so
  anything that read its level during import read the unconfigured default.
  That is what `dial/app.py` used to do with a module-level `_is_debug`.

A subprocess, because LOG_LEVEL has to be set before the root app is imported
and the suite shares one interpreter.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = next(
    p for p in Path(__file__).parents if (p / "pyproject.toml").is_file()
)

# One module per adapter, each reaching for the logger the way its own code
# does -- openai and the others by importing it, dial via __name__.
PROBE = """
import json, logging
import aidial_model_provider.app  # noqa: F401  -- calls configure_loggers()
from aidial_model_provider.bedrock.bedrock import log as bedrock_log
from aidial_model_provider.openai.utils.streaming import logger as openai_log
from aidial_model_provider.vertexai.chat_completion import log as vertexai_log
from aidial_model_provider.dial.app import _log as dial_log

root = logging.getLogger("aidial_model_provider")
print(json.dumps({
    "level": logging.getLevelName(root.level),
    "shared": {
        "bedrock": bedrock_log is root,
        "openai": openai_log is root,
        "vertexai": vertexai_log is root,
    },
    "dial_debug_enabled": dial_log.isEnabledFor(logging.DEBUG),
}))
"""


def test_log_level_reaches_every_adapter():
    env = {
        **os.environ,
        "LOG_LEVEL": "DEBUG",
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

    assert result["level"] == "DEBUG", (
        "configure_loggers() did not apply LOG_LEVEL to the "
        "aidial_model_provider logger"
    )
    for adapter, shared in result["shared"].items():
        assert shared, (
            f"the {adapter} adapter logs through a logger of its own; "
            "LOG_LEVEL will not reach it"
        )
    assert result["dial_debug_enabled"], (
        "the dial adapter decided its debug level before configure_loggers() "
        "ran -- check the level where it is used, not at import"
    )
