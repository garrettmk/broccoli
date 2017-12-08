import os
from celery import Celery


app = Celery(
    'broccoli',
    broker=os.environ.get('CLOUDAMQP_URL', 'pyamqp://guest:guest@rabbit:5672'),
    backend=os.environ.get('CLOUDAMQP_URL', 'amqp://').replace('amqp', 'rpc'),
    include=['broccoli.mws']
)

# Do configuration (throttling limits?) here
# app.conf.update()

if __name__ == '__main__':
    app.start()