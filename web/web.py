import os
import sys
import time
import logging
import rq, rq_dashboard
import redis
from flask import Flask, request, jsonify

redis_url = os.environ.get('REDIS_URL')
if not redis_url:
    raise RuntimeError('Set up Redis first.')

app = Flask(__name__)

# Set up RQ-Dashboard
app.config.update(
    REDIS_URL=redis_url,
    RQ_POLL_INTERVAL=2500,
)
app.register_blueprint(rq_dashboard.blueprint, url_prefix='/dashboard')

# Direct all logging to stdout. It will get picked up by supervisord
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.INFO)


conn = redis.Redis.from_url(redis_url)
queue = rq.Queue('high', connection=conn)


@app.route('/')
def hello():
    print('A printed message.')
    print('A message printed to stderr.', file=sys.stderr)

    return f'PYTHONUNBUFFERED={os.environ.get("PYTHONUNBUFFERED")}<br>FLASK_DEBUG={os.environ.get("FLASK_DEBUG")}'


@app.route('/api/<path:task>')
def api_call(task):
    task_name = task.replace('/', '.')
    args = [arg for arg, val in request.args.items() if not len(val)]
    kwargs = {arg: val for arg, val in request.args.items() if arg not in args}

    app.logger.info(f'Sending to queue "high": {task_name}(args={args}, kwargs={kwargs})')

    start_time = time.time()
    job = queue.enqueue(
        task_name,
        args=args,
        kwargs=kwargs,
        timeout=10,
    )

    now = start_time
    while not job.is_finished and now - start_time < 10:
        time.sleep(0.1)
        now = time.time()

    try:
        return jsonify(job.result)
    except Exception as e:
        return repr(e)


################################################################################################################################################################################################################################################


if __name__ == '__main__':
    app.run()