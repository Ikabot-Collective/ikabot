FROM python:3.12-slim

# Add labels to describe the Docker image
LABEL org.opencontainers.image.description="The image includes all the necessary dependencies and configurations to run Ikabot seamlessly."
LABEL org.opencontainers.image.source="https://github.com/Ikabot-Collective/ikabot"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /ikabot
COPY . .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .
RUN apt-get update && \ 
    apt-get install --no-install-recommends dnsutils -y && \
    apt-get clean  && \
    rm -rf /var/lib/apt/lists/*

CMD ["python3", "-m", "ikabot"]