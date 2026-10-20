FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY apps/api ./apps/api
COPY instruments ./instruments
COPY knowledge ./knowledge

ENV PYTHONPATH=apps/api
ENV PYTHONUNBUFFERED=1
ENV API_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "ai_cio.api"]
