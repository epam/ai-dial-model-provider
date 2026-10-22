import contextlib
import importlib
import json
from collections.abc import Generator
from typing import Any, Protocol

import httpx
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport
from openai import AsyncAzureOpenAI, AsyncOpenAI

from aidial_model_provider.openai.configuration.app_config import (
    ApplicationConfig,
)
from aidial_model_provider.openai.utils.request import get_app_config
from aidial_model_provider.openai.utils.upstream_headers import (
    _UPSTREAM_EXTRA_DATA_HEADER,
)
from tests.integration_tests.openai.constants import (
    TEST_DEPLOYMENTS_CONFIG,
)

_TEST_TIMEOUT = httpx.Timeout(30, connect=10)

# Four modules capture DIAL_URL from the environment at import time, by value,
# so whatever it held when the openai adapter was first imported is what they
# use for the whole session. This suite has always run with it unset -- DIAL
# file storage off, binaries returned inline as base64 -- but only because
# nothing else in the process had set it.
#
# That stopped being true once all the suites share one interpreter: the dial
# adapter's tests need DIAL_URL set before their app module is imported. So the
# condition this suite depends on is pinned here instead of inherited, using the
# same monkeypatch.setattr(<module>, "DIAL_URL", ...) the suite already uses to
# pin the opposite case (see test_session_tags.py).
_DIAL_URL_HOLDERS = [
    "aidial_model_provider.openai.dial_api.storage",
    "aidial_model_provider.openai.dial_api.sdk_adapter",
    "aidial_model_provider.openai.utils.session_tags",
    "aidial_model_provider.openai.chat_completions.anthropic",
]


@pytest.fixture(autouse=True)
def _dial_file_storage_disabled(monkeypatch):
    for name in _DIAL_URL_HOLDERS:
        monkeypatch.setattr(
            importlib.import_module(name), "DIAL_URL", None, raising=False
        )


@pytest.fixture
async def _app_instance():
    from aidial_model_provider.openai.app import create_app, lifespan

    app = create_app(app_config=TEST_DEPLOYMENTS_CONFIG.app_config)

    # The app carries no lifespan of its own -- aidial_model_provider.app
    # composes it, because Starlette would not run it on a mounted app -- so the
    # cache teardown it does has to be entered here.
    async with lifespan(app), LifespanManager(app):
        yield app


@pytest.fixture
async def test_app(_app_instance):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_app_instance, raise_app_exceptions=False),
        base_url="http://test-app.com",
        timeout=_TEST_TIMEOUT,
    ) as client:
        yield client


@pytest.fixture
def eliminate_empty_choices(_app_instance):
    app_config = get_app_config(_app_instance)
    app_config.ELIMINATE_EMPTY_CHOICES = True
    yield
    app_config.ELIMINATE_EMPTY_CHOICES = False


@contextlib.asynccontextmanager
async def create_test_client(
    app_config: ApplicationConfig, *, base_url: str = "http://test-app.com"
):
    from aidial_model_provider.openai.app import create_app, lifespan

    app = create_app(app_config=app_config)
    async with (
        lifespan(app),
        LifespanManager(app),
        httpx.AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),  # type: ignore
            base_url=base_url,
            timeout=_TEST_TIMEOUT,
        ) as client,
    ):
        yield client


class AzureOpenAIClientFactory(Protocol):
    def __call__(
        self,
        azure_deployment: str,
        *,
        max_retries: int | None = None,
        api_version: str | None = None,
        upstream_endpoint: str | None = None,
        upstream_key: str | None = None,
        upstream_extra_data: dict[str, Any] | None = None,
    ) -> AsyncAzureOpenAI: ...


@pytest.fixture
def create_azure_openai_client(
    test_app: httpx.AsyncClient,
) -> Generator[AzureOpenAIClientFactory, None, None]:
    def _create_client(
        azure_deployment: str,
        *,
        max_retries: int | None = None,
        api_version: str | None = None,
        upstream_endpoint: str | None = None,
        upstream_key: str | None = "test-upstream-api-key",
        upstream_extra_data: dict[str, Any] | None = None,
    ) -> AsyncAzureOpenAI:
        default_headers: dict[str, str] = {}
        if upstream_key is not None:
            default_headers["X-UPSTREAM-KEY"] = upstream_key
        if upstream_endpoint is not None:
            default_headers["X-UPSTREAM-ENDPOINT"] = upstream_endpoint
        if upstream_extra_data is not None:
            default_headers[_UPSTREAM_EXTRA_DATA_HEADER] = json.dumps(
                upstream_extra_data
            )

        return AsyncAzureOpenAI(
            azure_endpoint=str(test_app.base_url),
            http_client=test_app,
            azure_deployment=azure_deployment,
            api_key="test-adapter-api-key",
            api_version=api_version or "2024-12-01-preview",
            max_retries=max_retries or 0,
            default_headers=default_headers,
        )

    yield _create_client


class OpenAIClientFactory(Protocol):
    def __call__(
        self,
        *,
        max_retries: int | None = None,
        upstream_endpoint: str | None = None,
        upstream_key: str | None = None,
    ) -> AsyncOpenAI: ...


@pytest.fixture
def create_openai_client(
    test_app: httpx.AsyncClient,
) -> Generator[OpenAIClientFactory, None, None]:
    def _create_client(
        *,
        max_retries: int | None = None,
        upstream_endpoint: str | None = None,
        upstream_key: str | None = "test-upstream-api-key",
    ) -> AsyncOpenAI:
        default_headers: dict[str, str] = {}
        if upstream_key is not None:
            default_headers["X-UPSTREAM-KEY"] = upstream_key
        if upstream_endpoint is not None:
            default_headers["X-UPSTREAM-ENDPOINT"] = upstream_endpoint

        return AsyncOpenAI(
            base_url=f"{str(test_app.base_url)}/openai/v1",
            http_client=test_app,
            api_key="test-adapter-api-key",
            max_retries=max_retries or 0,
            default_headers=default_headers,
        )

    yield _create_client
