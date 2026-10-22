from contextlib import asynccontextmanager

import fastapi
from aidial_adapter_anthropic.passthrough import mount_anthropic_api
from aidial_client import AsyncDialClientPool
from aidial_sdk.exceptions import HTTPException as DialException
from fastapi import FastAPI
from openai import OpenAIError

from aidial_model_provider.openai.apis.anthropic import get_anthropic_client
from aidial_model_provider.openai.apis.openai import mount_openai_api
from aidial_model_provider.openai.configuration.app_config import (
    ApplicationConfig,
)
from aidial_model_provider.openai.exceptions.handlers import (
    adapter_exception_handler,
    fastapi_exception_handler,
)
from aidial_model_provider.openai.utils.auth import (
    get_assume_role_provider,
    get_azure_token_provider,
    get_sts_client,
)
from aidial_model_provider.openai.utils.cache import cache
from aidial_model_provider.openai.utils.http_client import (
    get_anthropic_httpx_client,
    get_http_client,
)
from aidial_model_provider.openai.utils.request import set_app_config
from aidial_model_provider.utils.log_config import logger


async def _close_dial_client_pool(pool: AsyncDialClientPool) -> None:
    await pool.aclose()


@cache(_close_dial_client_pool)
def get_dial_client_pool() -> AsyncDialClientPool:
    return AsyncDialClientPool()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    logger.info("Application shutdown")
    await get_http_client.clear()
    await get_anthropic_httpx_client.clear()
    await get_dial_client_pool.clear()
    await get_azure_token_provider.clear()
    await get_assume_role_provider.clear()
    await get_sts_client.clear()


def create_app(app_config: ApplicationConfig | None = None) -> FastAPI:
    app = FastAPI()

    set_app_config(app, app_config or ApplicationConfig.from_env())

    mount_openai_api(app, path="/openai")
    mount_anthropic_api(app, get_anthropic_client, path="/anthropic")

    app.add_exception_handler(fastapi.HTTPException, fastapi_exception_handler)

    for exc_class in [OpenAIError, DialException]:
        app.add_exception_handler(exc_class, adapter_exception_handler)

    return app


app = create_app()
