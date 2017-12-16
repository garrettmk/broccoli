import os
import sys
import logging
from celery import Celery
from flask import Flask, request, jsonify

app = Flask(__name__)

# Direct all logging to stdout. It will get picked up by supervisord
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.INFO)

celery_app = Celery(
    __name__,
    broker=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
    backend=os.environ.get('REDIS_URL', 'redis://redis:6379/0')
)


@app.route('/')
def hello():
    print('A printed message.')
    print('A message printed to stderr.', file=sys.stderr)

    return f'PYTHONUNBUFFERED={os.environ.get("PYTHONUNBUFFERED")}<br>FLASK_DEBUG={os.environ.get("FLASK_DEBUG")}'


@app.route('/api/<path:task>')
def api_call(task):
    task_name = task.replace('/', '.')
    queue_name = task.replace('/', '_')
    args = [arg for arg, val in request.args.items() if not len(val)]
    kwargs = {arg: val for arg, val in request.args.items() if arg not in args}

    app.logger.info(f'Sending to queue "{queue_name}": {task_name}(args={args}, kwargs={kwargs})')

    result = celery_app.send_task(
        name=task_name,
        queue=queue_name,
        args=args,
        kwargs=kwargs,
    )

    try:
        return jsonify(result.get(timeout=10))
    except Exception as e:
        return repr(e)
