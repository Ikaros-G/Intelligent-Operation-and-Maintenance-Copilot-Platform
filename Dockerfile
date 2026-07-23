FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY static ./static
COPY mcp_servers ./mcp_servers
RUN pip install .

RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/uploads /app/logs && chown -R appuser:appuser /app
USER appuser

EXPOSE 9900
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9900"]
