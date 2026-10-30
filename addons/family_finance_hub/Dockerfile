# syntax=docker/dockerfile:1
# Supervisor builds this directory alone. Fetch the same application sources; do not duplicate the UI or backend.
FROM scratch AS source
ARG RUNWAY_SOURCE=https://github.com/Vico07/Runway.git#feat/family-finance-hub-home
ADD ${RUNWAY_SOURCE} /source/

# The base images are pinned by digest (the tag is for reading); Dependabot moves the digests weekly.

# 1. Install the dependencies (pyproject.toml / poetry.lock) into a virtualenv with Poetry. The virtualenv gets no pip:
#    Runway never installs anything at run time, and pip's bundled libraries only add to what the image scan flags.
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS deps
ENV PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_OPTIONS_NO_PIP=true \
    POETRY_NO_INTERACTION=1
# Optional public CA bundle for managed build proxies; never retained in a layer.
RUN --mount=type=secret,id=proxy_ca_bundle \
    if [ -f /run/secrets/proxy_ca_bundle ]; then export PIP_CERT=/run/secrets/proxy_ca_bundle; fi; \
    pip install "poetry==2.5.1"
WORKDIR /app
COPY --from=source /source/pyproject.toml /source/poetry.lock ./
RUN --mount=type=secret,id=proxy_ca_bundle \
    if [ -f /run/secrets/proxy_ca_bundle ]; then export REQUESTS_CA_BUNDLE=/run/secrets/proxy_ca_bundle SSL_CERT_FILE=/run/secrets/proxy_ca_bundle; fi; \
    poetry install --only main --no-root --no-ansi

# 2. Build the web app (frontend/) into runway/static/app. It's plain files, so it's built once on the build machine
#    whatever the image's architecture.
FROM --platform=$BUILDPLATFORM node:26-slim@sha256:ec7758ee051e457b468b32bde57b0879010b325bb9862718e9615225ce4aaae1 AS web
WORKDIR /web/frontend
COPY --from=source /source/frontend/package.json /source/frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca_bundle \
    if [ -f /run/secrets/proxy_ca_bundle ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca_bundle; fi; \
    npm ci --no-audit --no-fund
COPY --from=source /source/frontend/ ./
RUN npm run build

# 3. The image itself: Python, that virtualenv and Runway, without Poetry or pip.
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

LABEL org.opencontainers.image.source="https://github.com/Vico07/Runway" \
      org.opencontainers.image.description="Runway: personal finance, forecasting and investments"

# Set by the release workflow (v1.2.3); shown in Settings.
ARG VERSION=dev

ENV RUNWAY_VERSION=$VERSION \
    PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUNWAY_DATA=/data \
    RUNWAY_HOST=0.0.0.0 \
    RUNWAY_PORT=8765 \
    TZ=America/New_York

# Debian's security fixes that came out after the base image was built (OpenSSL's, most often), and no pip: nothing
# runs it, and the libraries it bundles (msgpack, setuptools) are flagged by the image scan. ensurepip's copy goes too.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall --yes --no-cache-dir --root-user-action=ignore pip \
 && rm -rf /usr/local/lib/python3.*/ensurepip/_bundled

# Run as an ordinary user; your database lives in /data (mount a folder or volume there).
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin runway \
 && mkdir -p /data && chown runway:runway /data

# The code stays owned by root, so it's read-only for the user it runs as; the app writes only to /data.
WORKDIR /app
COPY --from=deps /app/.venv ./.venv
COPY --from=source /source/run.py /source/alembic.ini ./
COPY --from=source /source/runway ./runway
COPY --from=web /web/runway/static/app ./runway/static/app
COPY --from=source /source/extension ./extension
# Cloud checkouts may have private directory modes; runtime uid must read source and migration scripts.
RUN chmod -R a+rX /app/runway /app/extension && chmod a+r /app/run.py /app/alembic.ini

USER root
VOLUME ["/data"]
EXPOSE 8765

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('RUNWAY_PORT', '8765'), timeout=4)" || exit 1

CMD ["python", "-m", "runway.server.ha_addon"]
