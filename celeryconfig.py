import os

broker_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
result_backend = broker_url
imports = ('mws.products')
task_acks_late = True
worker_prefetch_multiplier = 1
redis_max_connections = 1
broker_pool_limit = 1