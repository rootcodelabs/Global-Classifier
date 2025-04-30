FROM python:3.12.4-bookworm

WORKDIR /app

COPY enrichment_requirements.txt .

RUN pip install --no-cache-dir -r enrichment_requirements.txt

COPY . .

EXPOSE 8005

CMD ["uvicorn", "data_enrichment_api:app", "--host", "0.0.0.0", "--port", "8005"]
