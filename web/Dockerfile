FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir Flask==3.1.1 psycopg2-binary==2.9.10 gunicorn==23.0.0
COPY web/ /app/
CMD ["gunicorn", "--bind", "0.0.0.0:8502", "--workers", "2", "app:app"]
