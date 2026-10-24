FROM python:3.12-slim

# Add labels to describe the Docker image
LABEL org.opencontainers.image.description="The image includes all the necessary dependencies and configurations to run Ikabot seamlessly."
LABEL org.opencontainers.image.source="https://github.com/Ikabot-Collective/ikabot"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps first: they rarely change, so this layer stays cached
RUN apt-get update && \
    apt-get install -y --no-install-recommends dnsutils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /ikabot

# Python deps before the source so code edits don't reinstall them
RUN pip install "requests[socks]" cryptography psutil python-dotenv

COPY . .
RUN pip install --no-deps -e .

CMD ["python3", "-m", "ikabot"]
