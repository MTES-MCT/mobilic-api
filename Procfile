web: gunicorn app:app --preload --workers=$WEB_CONCURRENCY --timeout=60 --max-requests=1000 --max-requests-jitter=100
release: flask db upgrade
postdeploy: flask db upgrade
worker: celery --app=app.celery worker -Q celery --loglevel=info --concurrency=1 --max-tasks-per-child=500 --max-memory-per-child=300000
workerexports: celery --app=app.celery worker -Q exports --loglevel=info --concurrency=1 --max-tasks-per-child=500 --max-memory-per-child=400000
