FROM apache/airflow:2.10.5-python3.11
USER airflow
RUN pip install --no-cache-dir beautifulsoup4==4.15.0 requests==2.32.3 psycopg2-binary==2.9.10
