FROM python:3.9-slim
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY constants.py .
COPY inference_wrapper.py .
COPY model_inference_api.py .
COPY model_inference.py .
COPY inference_pipeline.py .
COPY s3_ferry.py .
COPY utils.py .
COPY test_inference_wrapper.py .

ENV HF_HOME=/app/cache/

RUN mkdir -p /shared && chown appuser:appuser /shared && chmod 777 /shared
RUN mkdir -p /shared/models/testing && chown appuser:appuser /shared/models/testing && chmod 777 /shared/models/testing
RUN chown -R appuser:appuser /app
EXPOSE 8003
USER appuser

CMD ["uvicorn", "model_inference_api:app", "--host", "0.0.0.0", "--port", "8003"]