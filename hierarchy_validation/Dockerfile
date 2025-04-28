FROM python:3.9-slim
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY constants.py .
COPY hierarchy_validation_api.py .
COPY utils.py .

RUN mkdir -p /shared && chown appuser:appuser /shared && chmod 770 /shared
RUN chown -R appuser:appuser /app
EXPOSE 8009
USER appuser

CMD ["uvicorn", "hierarchy_validation_api:app", "--host", "0.0.0.0", "--port", "8009"]
