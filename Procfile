web: gunicorn app:app --preload --workers=2
release: flask db upgrade
postdeploy: flask db upgrade

