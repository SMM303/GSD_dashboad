FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel jaraco.context \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -c "from importlib.metadata import version; from packaging.version import Version; assert Version(version('jaraco.context')) >= Version('6.1.0'), version('jaraco.context'); assert Version(version('wheel')) >= Version('0.46.2'), version('wheel')"

# App source
COPY . .

# Non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
