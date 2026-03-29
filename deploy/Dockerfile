FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install gsutil (via google-cloud-sdk)
RUN apt-get update -qq && \
    apt-get install -y -q --no-install-recommends curl gnupg unzip && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
      | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    apt-get update -qq && \
    apt-get install -y -q --no-install-recommends google-cloud-cli && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install news-collector
COPY pyproject.toml uv.lock .python-version ./
COPY news_collector/ ./news_collector/
RUN uv tool install .

# Install swrite (latest release binary)
ARG SWRITE_VERSION=v0.3.0
RUN curl -fsSL "https://github.com/nlink-jp/swrite/releases/download/${SWRITE_VERSION}/swrite-linux-amd64.zip" \
      -o /tmp/swrite.zip && \
    unzip /tmp/swrite.zip -d /tmp/swrite && \
    cp /tmp/swrite/swrite-linux-amd64 /usr/local/bin/swrite && \
    chmod +x /usr/local/bin/swrite && \
    rm -rf /tmp/swrite*

# Copy deployment config
COPY deploy/topics.toml /app/topics.toml
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
