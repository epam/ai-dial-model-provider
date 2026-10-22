from contextlib import asynccontextmanager

from aidial_adapter_anthropic.passthrough import mount_anthropic_api
from aidial_sdk import DIALApp

from aidial_model_provider.vertexai.anthropic_passthrough import (
    get_anthropic_client,
)
from aidial_model_provider.vertexai.chat_completion import (
    VertexAIChatCompletion,
)
from aidial_model_provider.vertexai.clients import (
    get_anthropic_vertex_client,
    get_genai_client,
    get_httpx_client,
    get_mistral_gcp_client,
    init_vertex_ai,
)
from aidial_model_provider.vertexai.dial_api.exceptions import (
    dial_exception_decorator,
)
from aidial_model_provider.vertexai.dial_api.response import (
    ModelObject,
    ModelsResponse,
)
from aidial_model_provider.vertexai.embeddings import VertexAIEmbeddings
from aidial_model_provider.vertexai.utils.adapter_deployments import (
    get_static_deployments,
)
from aidial_model_provider.vertexai.utils.azure_auth import (
    close_azure_credential,
)
from aidial_model_provider.vertexai.vertex_ai import (
    get_multi_modal_embedding_model,
)


@asynccontextmanager
async def lifespan(_: DIALApp):
    init_vertex_ai()
    yield
    await get_httpx_client.clear()
    await get_genai_client.clear()
    await get_anthropic_vertex_client.clear()
    await get_multi_modal_embedding_model.clear()
    await get_mistral_gcp_client.clear()
    await close_azure_credential()


# No telemetry_config: telemetry belongs to aidial_model_provider.app, once per
# process. Passing None also leaves DIALApp's per-request otel context reset
# disabled, which is what lets the root app's request span stay current inside
# this one rather than being detached.
app = DIALApp(
    description="Google VertexAI adapter for DIAL API",
)

deployments = get_static_deployments()


@app.get("/openai/models")
@dial_exception_decorator
async def models():
    return ModelsResponse(
        data=list(map(ModelObject.chat_completions, deployments.chat))
        + list(map(ModelObject.embeddings, deployments.embeddings))
    )


app.add_chat_completion("{deployment_id}", VertexAIChatCompletion())
app.add_embeddings("{deployment_id}", VertexAIEmbeddings())

mount_anthropic_api(app, get_anthropic_client, path="/anthropic")
