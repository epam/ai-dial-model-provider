"""The composed lifespan, which is hand-written and therefore easy to get wrong.

Starlette does not run the lifespan of a mounted app, so the adapters' apps
carry none and aidial_model_provider.app enters theirs itself. Forgetting one
there is silent: the adapter serves requests normally and leaks whatever client
its lifespan would have closed.
"""

from contextlib import asynccontextmanager

import pytest

import aidial_model_provider.app as composition_root
from aidial_model_provider.bedrock.app import app as bedrock_app
from aidial_model_provider.bedrock.app import lifespan as bedrock_lifespan
from aidial_model_provider.openai.app import app as openai_app
from aidial_model_provider.openai.app import lifespan as openai_lifespan
from aidial_model_provider.vertexai.app import app as vertexai_app
from aidial_model_provider.vertexai.app import lifespan as vertexai_lifespan

# dial is absent on purpose: its app.py defines no lifespan. test_dial_still_has
# _no_lifespan below is what notices if an upstream sync gives it one.
COMPOSED = ["openai", "vertexai", "bedrock"]


@pytest.fixture
def events(monkeypatch) -> list[str]:
    """Replace each adapter's lifespan with one that records being entered."""
    recorded: list[str] = []

    def recorder(name: str):
        @asynccontextmanager
        async def _lifespan(_):
            recorded.append(f"{name}:start")
            yield
            recorded.append(f"{name}:stop")

        return _lifespan

    for name in COMPOSED:
        monkeypatch.setattr(
            composition_root, f"{name}_lifespan", recorder(name)
        )

    return recorded


async def test_every_adapter_lifespan_is_entered(events: list[str]):
    async with composition_root.lifespan(composition_root.app):
        assert events == [f"{name}:start" for name in COMPOSED]

    # and unwound in reverse, so an adapter never shuts down before one that
    # started after it
    assert events[len(COMPOSED) :] == [
        f"{name}:stop" for name in reversed(COMPOSED)
    ]


@pytest.mark.parametrize(
    ("subapp", "own_lifespan"),
    [
        (openai_app, openai_lifespan),
        (vertexai_app, vertexai_lifespan),
        (bedrock_app, bedrock_lifespan),
    ],
    ids=COMPOSED,
)
def test_adapters_do_not_carry_their_own_lifespan(subapp, own_lifespan):
    # Re-attaching it upstream would not break anything visibly -- Starlette
    # would simply never run it -- which is exactly why it is asserted here.
    assert subapp.router.lifespan_context is not own_lifespan


def test_dial_still_has_no_lifespan():
    import aidial_model_provider.dial.app as dial_module

    assert not hasattr(dial_module, "lifespan")
