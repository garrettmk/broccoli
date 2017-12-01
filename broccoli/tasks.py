import os
from celery import Celery


app = Celery(
    'tasks',
    broker=os.environ.get('MESSAGE_BROKER_URI', 'pyamqp://'),
    backend=os.environ.get('CELERY_BACKEND_URI', 'rpc://')
)


@app.task
def add(x, y):
    return x + y
