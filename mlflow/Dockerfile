FROM python:3.9-slim


COPY ./requirements.txt /mlflow/requirements.txt

RUN pip install --no-cache-dir -r /mlflow/requirements.txt

# Create directories for MLflow data with explicit permissions
RUN mkdir -p /mlflow/mlflow_data /mlflow/mlflow_artifacts && \
    chmod -R 777 /mlflow/mlflow_data /mlflow/mlflow_artifacts

WORKDIR /mlflow

# Copy any initialization files if needed
COPY ./entrypoint.sh /mlflow/entrypoint.sh
RUN chmod +x /mlflow/entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/mlflow/entrypoint.sh"]