import time

from celery import Celery

from app import app

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)


@celery.task
def add(x, y):
    app.logger.info("celery task starts")
    time.sleep(3)
    return x * y


@app.route("/toto")
def index():
    print("start")
    result = add.delay(4, 8)
    return "ok"
