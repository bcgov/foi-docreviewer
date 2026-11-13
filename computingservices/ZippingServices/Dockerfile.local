FROM python:3.13.17-trixie
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade libunbound8 \
    && rm -rf /var/lib/apt/lists/*

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN useradd --create-home --shell /bin/bash app_user
WORKDIR /home/app_user
COPY requirements.txt ./
RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
USER app_user
COPY . .
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
