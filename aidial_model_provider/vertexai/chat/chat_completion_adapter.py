from abc import ABC, abstractmethod
from typing import Any, Generic, Protocol, TypeVar

from aidial_sdk.chat_completion.request import ChatCompletionRequest

from aidial_model_provider.vertexai.chat.consumer import Consumer
from aidial_model_provider.vertexai.chat.errors import UserError
from aidial_model_provider.vertexai.chat.static_tools import StaticToolsConfig
from aidial_model_provider.vertexai.chat.tools import ToolsConfig
from aidial_model_provider.vertexai.chat.truncate_prompt import TruncatedPrompt
from aidial_model_provider.vertexai.dial_api.request import ModelParameters
from aidial_model_provider.vertexai.utils.not_implemented import not_implemented

P = TypeVar("P")


class _JSONSchemaProducer(Protocol):
    def model_json_schema(self) -> dict[str, Any]: ...


class ChatCompletionAdapter(ABC, Generic[P]):
    @abstractmethod
    async def parse_prompt(
        self,
        params: ModelParameters,
        tools: ToolsConfig,
        static_tools: StaticToolsConfig,
        request: ChatCompletionRequest,
    ) -> P | UserError:
        pass

    @abstractmethod
    async def chat(
        self, params: ModelParameters, consumer: Consumer, prompt: P
    ) -> None:
        pass

    @not_implemented
    async def configuration(self) -> _JSONSchemaProducer | None: ...

    @not_implemented
    async def truncate_prompt(
        self, prompt: P, max_prompt_tokens: int
    ) -> TruncatedPrompt[P]: ...

    @not_implemented
    async def count_prompt_tokens(self, prompt: P) -> int: ...

    @not_implemented
    async def count_completion_tokens(self, string: str) -> int: ...
