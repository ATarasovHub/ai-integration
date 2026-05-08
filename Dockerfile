FROM python:3.12-slim

LABEL org.opencontainers.image.title="ai-integration" \
      org.opencontainers.image.description="Jira -> LLM -> Rocket.Chat bot" \
      org.opencontainers.image.source="https://git.tech-on-air.com/atarasov/ai-integration" \
      org.opencontainers.image.authors="atarasov <tarasovandri10@gmail.com>" \
      org.opencontainers.image.version="1.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY assets/ ./assets/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
