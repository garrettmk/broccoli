import os
from redis import Redis
from rq import Queue, Connection
from rq.worker import HerokuWorker as Worker

import mws.products

listen_to = [
    'high',
    'default',
    'low'
]


redis_url = os.environ.get('REDIS_URL')
if not redis_url:
    raise RuntimeError('Set up Redis first.')

conn = Redis.from_url(redis_url)


if __name__ == '__main__':
    with Connection(conn):
        worker = Worker((Queue(name) for name in listen_to))
        worker.work()