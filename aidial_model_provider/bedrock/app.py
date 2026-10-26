from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aidial_adapter_anthropic.passthrough import mount_anthropic_api
from aidial_sdk import DIALApp
from fastapi import FastAPI

from aidial_model_provider.bedrock.anthropic_passthrough import (
    get_anthropic_client,
)
from aidial_model_provider.bedrock.anthropic_translator.chat_completions.app import (
    app as chat_completions_translator_app,
)
from aidial_model_provider.bedrock.bedrock import (
    create_anthropic_client,
    create_boto_client,
    get_anthropic_http_client,
    get_dial_client_pool,
)
from aidial_model_provider.bedrock.chat_completion import BedrockChatCompletion
from aidial_model_provider.bedrock.dial_api.response import (
    ModelObject,
    ModelsResponse,
)
from aidial_model_provider.bedrock.embeddings import BedrockEmbeddings
from aidial_model_provider.bedrock.server.exceptions import (
    dial_exception_decorator,
)
from aidial_model_provider.bedrock.upstream_config import get_sts_client
from aidial_model_provider.bedrock.utils.adapter_deployments import (
    get_static_deployments,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await create_anthropic_client.clear()
        await create_boto_client.clear()
        await get_sts_client.clear()
        await get_anthropic_http_client.clear()
        await get_dial_client_pool.clear()


# No telemetry_config: telemetry belongs to aidial_model_provider.app, once per
# process. Passing None also leaves DIALApp's per-request otel context reset
# disabled, which is what lets the root app's request span stay current inside
# this one rather than being detached.
app = DIALApp(
    description="AWS Bedrock adapter for DIAL API",
)

deployments = get_static_deployments()


@app.get("/openai/models")
@dial_exception_decorator
async def models():
    return ModelsResponse(
        data=list(map(ModelObject.chat_completions, deployments.chat))
        + list(map(ModelObject.embeddings, deployments.embeddings))
    )


app.add_chat_completion("{deployment_id}", BedrockChatCompletion())
app.add_embeddings("{deployment_id}", BedrockEmbeddings())


mount_anthropic_api(app, get_anthropic_client, path="/anthropic")

app.mount(
    path="/openaiChatCompletions",
    app=chat_completions_translator_app,
    name="Anthropic Messages to Chat Completions translator",
)
