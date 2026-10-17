
FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies before copying application source.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user.
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup appuser

COPY --chown=appuser:appgroup app/ ./app/

USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
