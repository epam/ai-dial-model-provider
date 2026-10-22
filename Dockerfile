# One image serving every adapter (docs/design.md §4). alpine and geos-dev
# come from the vertexai adapter, the tiktoken cache from the openai one; the
# rest is what all four Dockerfiles already had in common.
FROM python:3.11-alpine AS builder

RUN apk update && apk upgrade --no-cache libcrypto3 libssl3
RUN apk add --no-cache alpine-sdk linux-headers geos-dev
RUN pip install poetry==2.1.1

WORKDIR /app

# Dependencies and sources are copied separately so that a source-only change
# does not re-resolve the (single, large) dependency set.
COPY pyproject.toml poetry.lock poetry.toml ./
RUN poetry install --no-interaction --no-ansi --no-cache --no-root \
  --no-directory --only main

# pip is not needed to run the server, and the venv is copied whole into the
# final stage -- so its pip, and the CVEs in it, would travel along.
RUN .venv/bin/python -m pip uninstall -y pip

# Download tiktoken model encodings
ENV TIKTOKEN_CACHE_DIR=/app/tiktoken_cache
RUN .venv/bin/python -c "from tiktoken.model import (get_encoding as load, MODEL_TO_ENCODING as models); [(print(f'Loading tiktoken tokenizer {e}...'), load(e)) for e in set(models.values())]"

# package-mode = false: the sources are run from /app, not installed into the
# venv, so copying them is the whole "build". The package holds nothing but the
# server -- every test tree lives in ./tests -- so it is copied whole.
COPY aidial_model_provider aidial_model_provider

FROM python:3.11-alpine AS server

RUN apk update && apk upgrade --no-cache libcrypto3 libssl3

# Updating the system CA bundle at /etc/ssl/certs/ca-certificates.crt
RUN apk add --no-cache ca-certificates mailcap && update-ca-certificates

# fix CVE-2026-85091 and CVE-2026-107891
RUN apk upgrade --no-cache musl musl-utils zlib
# fix CVE-2026-59890, and CVE-2026-23949 and CVE-2026-24049 in the copies of
# jaraco.context and wheel that setuptools vendors -- a top-level `pip install
# wheel` does not reach those.
RUN pip install setuptools==83.0.0
# pip is not needed at runtime; removing it fixes every pip CVE. Must stay
# after the install above.
RUN pip uninstall -y pip

WORKDIR /app

# Copy the sources and virtual env. No poetry.
RUN adduser -u 1001 --disabled-password --gecos "" appuser
COPY --chown=appuser --from=builder /app .

COPY ./scripts/__cacert_entrypoint.sh /__cacert_entrypoint.sh
RUN chmod +x /__cacert_entrypoint.sh

COPY ./scripts/docker_entrypoint.sh /docker_entrypoint.sh
RUN chmod +x /docker_entrypoint.sh

EXPOSE 5000

USER appuser

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

ENV TIKTOKEN_CACHE_DIR=/app/tiktoken_cache
ENV PYDANTIC_V2=1
ENV LOG_LEVEL=INFO

ENTRYPOINT ["/docker_entrypoint.sh"]
