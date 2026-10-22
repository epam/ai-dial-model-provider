from openai.types.create_embedding_response import CreateEmbeddingResponse

from aidial_model_provider.openai.utils.auth import OpenAICreds
from aidial_model_provider.openai.utils.parsers import embeddings_parser
from aidial_model_provider.openai.utils.reflection import call_with_extra_body


async def embeddings(
    *,
    request: dict,
    creds: OpenAICreds,
    endpoint: str,
    api_version: str | None,
    headers: dict[str, str] | None = None,
) -> CreateEmbeddingResponse:
    client = embeddings_parser.parse(endpoint).get_client(
        {**creds, "api_version": api_version, "headers": headers or {}}
    )

    return await call_with_extra_body(client.embeddings.create, request)
