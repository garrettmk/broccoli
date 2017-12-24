import os
from celery import Celery


########################################################################################################################


app = Celery(
    'worker',
    broker=os.environ.get('REDIS_URL', 'redis://'),
    backend=os.environ.get('REDIS_URL' 'redis://'),
    include=[
        'mws.products',
        'mws.product_adv',
        'parsed.products',
        'parsed.product_adv',
        'ops.spiders'
    ]
)


########################################################################################################################


if __name__ == '__main__':
    app.start()
