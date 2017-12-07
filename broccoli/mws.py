import os
import re
import requests
import pymongo
import functools
import lib.amazonmws.amazonmws as mws
from lxml import etree
from datetime import datetime, timedelta
from celery import Task
from .celery import app


def with_requests(method, **kwargs):
    """Uses the requests library for amazonmws."""
    if method == 'POST':
        return requests.post(**kwargs)
    elif method == 'GET':
        return requests.get(**kwargs)
    else:
        raise ValueError('Invalid HTTP method: ' + method)


credentials = {
    'access_key': os.environ.get('MWS_ACCESS_KEY'),
    'secret_key': os.environ.get('MWS_SECRET_KEY'),
    'account_id': os.environ.get('MWS_ACCOUNT_ID')
}


apis = {
    'Products': mws.Products(**credentials, make_request=with_requests)
}

mongo_db = None


def get_cache_collection():
    """Return the Mongo database that contains the API cache."""
    if mongo_db is None:
        uri = os.environ.get('MONGO_URI', '')
        db = os.environ.get('MONGO_DB', 'miranda')
        coll = os.environ.get('CACHE_COLLECTION', 'broccoli')

        client = pymongo.MongoClient(uri)
        mongo_db = client[db]

    return mongo_db[coll]


def use_cache(days=3):
    """Decorator that checks the database an API response."""

    def _real_use_cache(task):

        def _memo(*args, **kwargs):
            filter = {
                'task': task.__name__,
                'args': args,
                'kwargs': kwargs,
                'status': 'SUCCESS',
            }

            collection = get_cache_collection()
            prev_call = collection.find_one(filter=filter, sort=pymongo.DESCENDING)

            if prev_call is not None \
                    and prev_call['timestamp'] >= datetime.utcnow() - timedelta(days=days):
                return prev_call['results']
            else:
                results = task(*args, **kwargs)
                collection.insert_one({
                    'task': task.__name__,
                    'args': args,
                    'kwargs': kwargs,
                    'status': 'S'
                })

        return _memo

    return _real_use_cache


def remove_namespaces(xml):
    """Remove all traces of namespaces from the given XML string."""
    re_ns_decl = re.compile(r' xmlns(:\w*)?="[^"]*"', re.IGNORECASE)
    re_ns_open = re.compile(r'<\w+:')
    re_ns_close = re.compile(r'/\w+:')

    response = re_ns_decl.sub('', xml)  # Remove namespace declarations
    response = re_ns_open.sub('<', response)  # Remove namespaces in opening tags
    response = re_ns_close.sub('/', response)  # Remove namespaces in closing tags
    return response


def xpath_get(tag, path, _type=str, default=None):
    """Utility method for getting data values from XPath selectors."""
    try:
        data = tag.xpath(path)[0].text
        if _type is str and data is None:
            raise TypeError
        else:
            return _type(data)
    except (IndexError, ValueError, TypeError):
        return default


class MWSTask(Task):
    """Base behaviors for all MWS api calls."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Store failed calls for later inspection."""


@app.task(base=MWSTask, bind=True, rate_limit='12/m')
@use_cache(days=1)
def GetServiceStatus(service):
    """Return the status of the given service."""
    result = apis[service].GetServiceStatus()

    xml = remove_namespaces(result.text)
    tree = etree.fromstring(xml)

    return tree.xpath('.//Status')[0].text
