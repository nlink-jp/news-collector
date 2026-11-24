# news-collector — Cloud Run Job image (linux/amd64).
#
# Every input is pinned and checked, so a rebuild installs what was reviewed:
#   - the base and uv images by their multi-arch index digest
#   - the Python dependencies from uv.lock, whose hashes uv verifies
#   - swrite by exact release and SHA-256
# Only Debian's own updates (signed, verified by apt) arrive on a rebuild, via
# `apt-get upgrade`. To move a pinned input, edit it here and release that.
# Rebuild with --no-cache so the apt layer actually runs again.

FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

FROM python:3.11-slim@sha256:61e01f72680f86a5279ad510818ab7b2ee9f049822589d4e34e33e044360356c AS base

# swrite (Slack posting): one exact release, checked before it is unpacked.
FROM base AS swrite
ARG SWRITE_VERSION=v0.5.1
ARG SWRITE_SHA256_AMD64=be0d4513d7fd71fc1416686097138f1f3fe740eafb54d6eb77ece0160cc27c38
RUN set -eu; \
    python3 -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/tmp/swrite.tar.gz')" \
      "https://github.com/nlink-jp/swrite/releases/download/${SWRITE_VERSION}/swrite-${SWRITE_VERSION}-linux-amd64.tar.gz"; \
    echo "${SWRITE_SHA256_AMD64}  /tmp/swrite.tar.gz" | sha256sum -c -; \
    mkdir /tmp/swrite; \
    tar -xzf /tmp/swrite.tar.gz -C /tmp/swrite swrite; \
    install -m 0755 /tmp/swrite/swrite /usr/local/bin/swrite

FROM base

# gsutil (via google-cloud-cli from Google's signed apt repository), plus the
# Debian security updates the pinned base predates.
RUN set -eu; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update -qq; \
    apt-get upgrade -y -q; \
    apt-get install -y -q --no-install-recommends ca-certificates curl gnupg; \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list; \
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
      | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg; \
    apt-get update -qq; \
    apt-get install -y -q --no-install-recommends google-cloud-cli; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv
COPY --from=swrite /usr/local/bin/swrite /usr/local/bin/swrite

WORKDIR /app

# Dependencies come from uv.lock only. The project itself is not built: its
# build backend (setuptools) is not in the lock, so building it would fetch
# an unchecked package. The package runs from its source directory instead.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY news_collector/ ./news_collector/
RUN printf '#!/bin/sh\nexec /opt/venv/bin/python -m news_collector.cli "$@"\n' > /usr/local/bin/news-collector; \
    chmod 0755 /usr/local/bin/news-collector

# Fail the build if the installed tools do not start.
RUN news-collector --help > /dev/null && swrite --version && gsutil version > /dev/null

# Copy deployment config
COPY deploy/topics.toml /app/topics.toml
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
