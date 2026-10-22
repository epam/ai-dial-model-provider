import os

# aidial_model_provider.app imports the four adapters statically, and the dial
# adapter's app.py calls AppConfig.from_env() at import time, so DIAL_URL has to
# be in the environment before any test module is imported -- a fixture would
# run too late.
#
# It lives in THIS conftest, not in tests/ or in pyproject's pytest `env` block,
# because it must not reach the adapters' own suites: the openai adapter binds
# DIAL_URL into a module constant, and a non-empty value there sends its dalle3
# images to a storage backend that does not exist.
os.environ.setdefault("DIAL_URL", "http://localhost:8080")
