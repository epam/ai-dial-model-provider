from contextlib import asynccontextmanager

from aidial_sdk.telemetry.init import init_telemetry as sdk_init_telemetry
from aidial_sdk.telemetry.types import TelemetryConfig
from fastapi import FastAPI

from aidial_model_provider.bedrock.app import app as bedrock_app
from aidial_model_provider.bedrock.app import lifespan as bedrock_lifespan
from aidial_model_provider.dial.app import app as dial_app
from aidial_model_provider.openai.app import app as openai_app
from aidial_model_provider.openai.app import lifespan as openai_lifespan
from aidial_model_provider.utils.log_config import configure_loggers
from aidial_model_provider.vertexai.app import app as vertexai_app
from aidial_model_provider.vertexai.app import lifespan as vertexai_lifespan


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with (
        openai_lifespan(openai_app),
        vertexai_lifespan(vertexai_app),
        bedrock_lifespan(bedrock_app),
    ):
        yield


async def health() -> dict[str, str]:
    return {"status": "ok"}


app = FastAPI(title="DIAL model adapter", lifespan=lifespan)

sdk_init_telemetry(app, TelemetryConfig())
configure_loggers()

app.get("/health")(health)

app.mount("/compat/openai", openai_app)
app.mount("/compat/vertexai", vertexai_app)
app.mount("/compat/bedrock", bedrock_app)
app.mount("/compat/dial", dial_app)
