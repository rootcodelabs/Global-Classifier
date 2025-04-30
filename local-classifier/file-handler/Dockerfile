FROM python:3.9-slim
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY file_handler_api.py .
COPY file_converter.py .
COPY constants.py .
COPY s3_ferry.py .
COPY dataset_deleter.py .

RUN mkdir -p /shared && chown appuser:appuser /shared && chmod 770 /shared
RUN chown -R appuser:appuser /app
EXPOSE 8000
USER appuser

CMD ["uvicorn", "file_handler_api:app", "--host", "0.0.0.0", "--port", "8000"]
