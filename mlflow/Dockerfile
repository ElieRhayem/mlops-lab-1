FROM python:3.13-slim

RUN pip install --no-cache-dir mlflow

EXPOSE 5000

CMD ["mlflow","server","--host","0.0.0.0","--port", "5000","--backend-store-uri", "sqlite:////mlflow-data/mlflow.db","--artifacts-destination","/mlflow-data/mlruns","--allowed-hosts", "mlflow:*,localhost:*,127.0.0.1:*"]
