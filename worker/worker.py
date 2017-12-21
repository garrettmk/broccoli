import os
from celery import Celery


########################################################################################################################


app = Celery(
    'worker',
    broker=os.environ['REDIS_URL'],
    backend=os.environ['REDIS_URL'],
    include=[
        'mws.products',
        'parsed.products',
        'spiders'
    ]
)


########################################################################################################################


if __name__ == '__main__':
    app.start()
