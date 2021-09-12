web: gunicorn app:app --preload --workers=4
release: flask db upgrade
postdeploy: flask db upgrade

