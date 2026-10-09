FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

# Runtime data (allowed users, preferences) is mounted here as a volume
VOLUME ["/app/data"]

RUN useradd --create-home --uid 1000 botuser
USER botuser

CMD ["python", "-m", "bot"]
