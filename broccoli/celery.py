import os
from celery import Celery


app = Celery(
    'broccoli',
    broker=os.environ.get('CLOUDAMQP_URL', 'pyamqp://'),
    backend='rpc://' + os.environ.get('CLOUDAMQP_URL', ':').split(':')[1],
    include=['broccoli.tasks']
)

# Do configuration (throttling limits?) here
app.conf.update(
    result_expires=3600
)

if __name__ == '__main__':
    app.start()