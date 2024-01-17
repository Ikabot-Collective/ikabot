FROM python:3

# Add labels to describe the Docker image
LABEL org.opencontainers.image.description="The image includes all the necessary dependencies and configurations to run Ikabot seamlessly."
LABEL org.opencontainers.image.source="https://github.com/physics-sec/ikabot"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /ikabot
COPY . .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -e .
RUN apt-get update
RUN apt-get install dnsutils -y

CMD "python3" "-m" "ikabot"