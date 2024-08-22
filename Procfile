web: gunicorn app:app --preload --workers=2 --timeout=120
release: flask db upgrade
postdeploy: flask db upgrade
worker: celery --app=app.celery worker --loglevel=info --concurrency=1
