FROM python:3.12.4-bookworm

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from transformers import pipeline; pipeline('ner', model='xlm-roberta-large-finetuned-conll03-english')"

COPY . .

EXPOSE 8010

CMD ["uvicorn", "anonymizer_api:app", "--host", "0.0.0.0", "--port", "8010"]