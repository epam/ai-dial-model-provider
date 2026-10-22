"""Fixtures for the vertexai suite, shared by its unit and integration trees.

They live in `tests/fixtures/vertexai.py` because conftest fixtures are
directory-scoped and this suite is split across `tests/unit_tests/vertexai` and
`tests/integration_tests/vertexai`. The names are re-exported one by one rather than
with `import *`, which skips the underscore-prefixed ones -- and those include
the autouse fixtures, whose absence would not be an import error, just a
silently different test run.

Keep this list in step with `tests/fixtures/vertexai.py` on every upstream sync.
"""

from tests.fixtures.vertexai import (  # noqa: F401
    configure_unit_tests,
    get_openai_client,
    test_http_client,
)
