"""Fixtures for the openai suite, shared by its unit and integration trees.

They live in `tests/fixtures/openai.py` because conftest fixtures are
directory-scoped and this suite is split across `tests/unit_tests/openai` and
`tests/integration_tests/openai`. The names are re-exported one by one rather than
with `import *`, which skips the underscore-prefixed ones -- and those include
the autouse fixtures, whose absence would not be an import error, just a
silently different test run.

Keep this list in step with `tests/fixtures/openai.py` on every upstream sync.
"""

from tests.fixtures.openai import (  # noqa: F401
    _app_instance,
    _dial_file_storage_disabled,
    create_azure_openai_client,
    create_openai_client,
    eliminate_empty_choices,
    test_app,
)
