FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY apps/api ./apps/api
COPY instruments ./instruments
COPY knowledge ./knowledge

ENV PYTHONPATH=apps/api
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "ai_cio.api"]
