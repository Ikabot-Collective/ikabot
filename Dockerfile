FROM python:3

LABEL org.opencontainers.image.description="The image includes all the necessary dependencies and configurations to run Ikabot seamlessly."
LABEL org.opencontainers.image.source="https://github.com/physics-sec/ikabot"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /ikabot
COPY . .

RUN ["python3", "-m", "pip", "install", "--user", "-e", "."]

CMD "python3" "-m" "ikabot"