"""Fixtures for the bedrock suite, shared by its unit and integration trees.

They live in `tests/fixtures/bedrock.py` because conftest fixtures are
directory-scoped and this suite is split across `tests/unit_tests/bedrock` and
`tests/integration_tests/bedrock`. The names are re-exported one by one rather than
with `import *`, which skips the underscore-prefixed ones -- and those include
the autouse fixtures, whose absence would not be an import error, just a
silently different test run.

Keep this list in step with `tests/fixtures/bedrock.py` on every upstream sync.
"""

from tests.fixtures.bedrock import (  # noqa: F401
    configure_unit_tests,
    get_openai_client,
    test_http_client,
)
