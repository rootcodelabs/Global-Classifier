FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/huggingface

RUN pip install --no-cache-dir uv==0.12.22 \
    && useradd --create-home --uid 10001 app

WORKDIR /app

# CPU-only torch comes from the PyTorch CPU index pinned in uv.lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && rm -rf /root/.cache

# Bake the pinned model weights in, so production never downloads from Hugging
# Face. Only the encoder and the model list come first, so other code changes
# don't download them again.
COPY embedding_classifier/__init__.py embedding_classifier/encoder.py embedding_classifier/embedding_models.json embedding_classifier/
COPY service/download_models.py service/download_models.py
ARG EMBEDDING_MODELS=multilingual-e5-large-instruct
ENV EMBEDDING_MODELS=${EMBEDDING_MODELS}
RUN python -m service.download_models ${EMBEDDING_MODELS} \
    && chmod -R a+rX ${HF_HOME}
ENV HF_HUB_OFFLINE=1

# The service image holds only the core library and the service
COPY embedding_classifier/ embedding_classifier/
COPY service/ service/

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v2/health/ready', timeout=4)" || exit 1

# One worker per container: encoding is serialised inside it
CMD ["uvicorn", "service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
