web: gunicorn app:app --preload --workers=$WEB_CONCURRENCY --timeout=60 --max-requests=1000 --max-requests-jitter=100
release: flask db upgrade
postdeploy: flask db upgrade
worker: celery --app=app.celery worker --loglevel=info --concurrency=1
