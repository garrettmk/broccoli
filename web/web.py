import os
import sys
import logging
import celery
from flask import Flask, request, jsonify


########################################################################################################################


app = Flask(__name__)
celery_app = celery.Celery(
    'web',
    broker=os.environ['REDIS_URL'],
    backend=os.environ['REDIS_URL']
)

# Direct all logging to stdout. It will get picked up by supervisord
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.INFO)


########################################################################################################################


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

    job = celery_app.send_task(
        task_name,
        args=args,
        kwargs=kwargs,
        expires=30
    )

    try:
        return jsonify(job.get(timeout=30))
    except Exception as e:
        return repr(e)


########################################################################################################################


if __name__ == '__main__':
    app.run()