# Dockerfile

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==1.8.4"

WORKDIR /app

# Copy only dependency metadata first (better cache)
COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-root --only main

# Now copy the rest of the project
COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
