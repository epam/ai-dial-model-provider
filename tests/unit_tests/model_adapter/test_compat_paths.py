"""The compat path table, checked against the four real adapters.

The app is built at import, from the real adapter packages, so this fails if an
adapter stops being importable, renames its DIAL route, or grows a new
import-time requirement — the ways the arrangement can break when the next
upstream sync lands.

The prefixes are spelled out rather than read from the app: a mount that was
dropped should fail here, which it cannot do if the expectation comes from the
code under test.
"""

import pytest
from fastapi.testclient import TestClient

from aidial_model_provider.app import app

ADAPTERS = ["openai", "vertexai", "bedrock", "dial"]


@pytest.fixture(scope="module")
def client():
    # raise_server_exceptions=False is what a real ASGI server does. The dial
    # adapter registers a catch-all `exception_handler(Exception)`, which
    # Starlette serves through ServerErrorMiddleware: it sends the handler's
    # response and re-raises for the server log. Left at the default, TestClient
    # would surface that re-raise instead of the 400 the client actually gets.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health_is_served_by_the_process(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_only_the_process_serves_health(client, adapter):
    # Each adapter defines one upstream -- a route for openai and dial,
    # add_healthcheck=True for vertexai's and bedrock's DIALApp. Four of them
    # behind a load balancer answer for the process while saying nothing about
    # it, so only the root app's survives. A sync that restores one makes this
    # path 200 again.
    assert client.get(f"/compat/{adapter}/health").status_code == 404


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_chat_completions_reaches_the_adapter(client, adapter):
    path = f"/compat/{adapter}/openai/deployments/gpt-4/chat/completions"
    response = client.post(
        path, json={"messages": [{"role": "user", "content": "hi"}]}
    )

    # A DIAL error envelope is the adapter's own request validation talking: it
    # rejects the request for a missing api-key or upstream endpoint, which means
    # the request arrived. Starlette's own 404 (`{"detail": "Not Found"}`) would
    # mean the mount point or the route tail is wrong — the failure worth
    # catching here. The status is not asserted: which 4xx/5xx each adapter picks
    # for a missing header is its business and does change upstream (the openai
    # adapter answers 500 for a missing X-UPSTREAM-ENDPOINT, the other three 400).
    assert response.status_code != 404, response.text
    assert "error" in response.json(), response.text


def test_unknown_prefix_is_not_served(client):
    path = "/compat/nope/openai/deployments/gpt-4/chat/completions"
    assert client.post(path, json={}).status_code == 404
