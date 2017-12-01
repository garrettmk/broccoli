import os
from celery import Celery


app = Celery(
    'broccoli',
    broker=os.environ.get('MESSAGE_BROKER_URI', 'pyamqp://'),
    backend=os.environ.get('CELERY_BACKEND_URI', 'rpc://'),
    include=['broccoli.tasks']
)

# Do configuration (throttling limits?) here
app.conf.update(
    result_expires=3600
)

if __name__ == '__main__':
    app.start()