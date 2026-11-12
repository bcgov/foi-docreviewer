FROM python:3.13-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl netbase wget libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash app_user
WORKDIR /home/app_user
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
USER app_user
COPY . .
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
