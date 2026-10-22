"""Fixtures for the openai suite, shared by its unit and integration trees.

They live in `tests/fixtures/openai.py` because conftest fixtures are
directory-scoped and this suite is split across `tests/unit_tests/openai` and
`tests/integration_tests/openai`. The names are re-exported one by one rather than
with `import *`, which skips the underscore-prefixed ones -- and those include
the autouse fixtures, whose absence would not be an import error, just a
silently different test run.

`create_openai_client` is deliberately not among them: this tree defines its
own, built from a DeploymentConfig rather than raw upstream headers.

Keep this list in step with `tests/fixtures/openai.py` on every upstream sync.
"""

import httpx
import pytest
from openai import AsyncAzureOpenAI

from tests.fixtures.openai import (  # noqa: F401
    _app_instance,
    _dial_file_storage_disabled,
    create_azure_openai_client,
    eliminate_empty_choices,
    test_app,
)
from tests.integration_tests.openai.base import (
    DeploymentConfig,
)
from tests.utils.openai.http_client import (
    with_request_overrides,
)


@pytest.fixture
# F811: `test_app` is re-exported above and consumed here by name, which is
# how pytest injects it. Both are required; neither is a real redefinition.
def create_openai_client(test_app: httpx.AsyncClient):  # noqa: F811
    def _create_client(deployment_config: DeploymentConfig) -> AsyncAzureOpenAI:
        return AsyncAzureOpenAI(
            azure_endpoint=str(test_app.base_url),
            azure_deployment=deployment_config.id_,
            api_version="2024-12-01-preview",
            api_key="dummy_key",
            max_retries=3,
            http_client=with_request_overrides(
                test_app, deployment_config.model_defaults
            ),
            default_headers=deployment_config.upstream_headers,
        )

    yield _create_client
