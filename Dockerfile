FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    APP_ENV=production \
    DATABASE_PATH=/data/quiz_progress.sqlite3

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY web_app.py ./
COPY fsrs45.py ./
COPY templates ./templates
COPY static ./static
COPY voc_database.csv exam_list.csv ./

RUN mkdir -p /data && chown 10001:10001 /data
VOLUME ["/data"]
USER 10001:10001
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "960", "web_app:app"]
