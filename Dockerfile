FROM python:3

WORKDIR /ikabot
COPY . .

RUN ["python3", "-m", "pip", "install", "--user", "-e", "."]

CMD "python3" "-m" "ikabot"