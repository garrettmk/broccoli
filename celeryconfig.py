broker_url = 'redis://redis:6379/0'
result_backend = 'redis://redis:6379/0'
imports = ('mws.products')
task_acks_late = True
worker_prefetch_multiplier = 1