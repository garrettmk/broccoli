import functools
import hashlib
import json
import os
import re
import redis
import requests
import lib.amazonmws.amazonmws as amz_mws
import celeryconfig
from celery import Celery, Task
from celery.utils.log import get_task_logger
from lxml import etree


########################################################################################################################


mws_priority_quotas = {
    0: {
        'GetServiceStatus': 1,
        'ListMatchingProducts': 1
    },
    1: {
        'GetServiceStatus': 2,
        'ListMatchingProducts': 5,
    },
    2: {
        'GetServiceStatus': 2,
        'ListMatchingProducts': 14
    }
}


########################################################################################################################


class AmzXmlResponse:
    """A utility class for dealing with Amazon's XML responses."""

    def __init__(self, xml=None):
        self._xml = None
        self.tree = None

        self.xml = xml

    @property
    def xml(self):
        return self._xml

    @xml.setter
    def xml(self, xml):
        """Perform automatic etree parsing."""
        self._xml, self.tree = None, None

        if xml is not None:
            self._xml = self.remove_namespaces(xml)
            self.tree = etree.fromstring(self._xml)

    @staticmethod
    def remove_namespaces(xml):
        """Remove all traces of namespaces from the given XML string."""
        re_ns_decl = re.compile(r' xmlns(:\w*)?="[^"]*"', re.IGNORECASE)
        re_ns_open = re.compile(r'<\w+:')
        re_ns_close = re.compile(r'/\w+:')

        response = re_ns_decl.sub('', xml)  # Remove namespace declarations
        response = re_ns_open.sub('<', response)  # Remove namespaces in opening tags
        response = re_ns_close.sub('/', response)  # Remove namespaces in closing tags
        return response

    def xpath_get(self, path, root_tag=None, _type=str, default=None):
        """Utility method for getting data values from XPath selectors."""
        tag = root_tag if root_tag is not None else self.tree
        try:
            data = tag.xpath(path)[0].text
            if _type is str and data is None:
                raise TypeError
            else:
                return _type(data)
        except (IndexError, ValueError, TypeError):
            return default

    @property
    def error_code(self):
        """Holds the error code if the response was an error, otherwise None."""
        if self.tree is None:
            return None

        return self.xpath_get('/ErrorResponse/Error/Code')

    @property
    def error_message(self):
        """Holds the error message if the response was an error, otherwise None."""
        if self.tree is None:
            return None

        return self.xpath_get('/ErrorResponse/Error/Message')

    @property
    def request_id(self):
        """Returns the RequestID parameter."""
        if self.tree is None:
            return None

        return self.xpath_get('//RequestID')

    def error_as_json(self):
        """Formats an error response as a simple JSON object."""
        return {
            'error': {
                'code': self.error_code,
                'message': self.error_message,
                'request_id': self.request_id
            }
        }


class MWSTask(Task):
    """Base behaviors for all MWS API calls."""
    def __init__(self):
        self.products = self.get_api('Products')
        self.redis = redis.Redis.from_url(self.app.conf.broker_url)  # TODO: add configuration via env

    def __call__(self, *args, **kwargs):
        """Provides common behaviors for all MWS api calls."""
        logger = get_task_logger(__name__)

        priority_ceil = max(mws_priority_quotas)
        try:
            priority = min(int(kwargs.pop('priority', '0')), priority_ceil)
        except TypeError:
            priority = 0

        # If a priority level is provided, update the API throttler's
        # quota_max settings.
        quota_maxes = mws_priority_quotas[priority]

        for action, quota in quota_maxes.items():
            self.products.limits[action]['quota_max'] = quota

        op_name = self.name.split('.')[-1]
        logger.info(f'Wait for {op_name}: {self.products.calculate_wait(op_name)}')

        return super().__call__(*args, **kwargs)

    @staticmethod
    def _use_requests(method, **kwargs):
        """Adapter function that lets the amazonmws library use requests."""
        if method == 'POST':
            return requests.post(**kwargs)
        elif method == 'GET':
            return requests.get(**kwargs)
        else:
            raise ValueError('Unsupported HTTP method: ' + method)

    def get_api(self, name):
        """Return an API object for the given API section (aka 'Reports', 'Products', etc.)"""
        credentials = {
            'access_key': os.environ.get('MWS_ACCESS_KEY', 'test_access_key'),
            'secret_key': os.environ.get('MWS_SECRET_KEY', 'test_secret_key'),
            'seller_id': os.environ.get('MWS_SELLER_ID', 'test_account_id')
        }

        return amz_mws.Throttler(
            getattr(amz_mws, name)(**credentials, make_request=self._use_requests)
        )

    def build_cache_key(self, action, args, kwargs):
        """Build a cache key from the given action and call signature."""
        sig = hashlib.md5(
            json.dumps({'args': args, 'kwargs': kwargs}).encode()
        ).hexdigest()

        return action + sig


def use_redis_cache(cache_ttl):
    """Decorator for MWS tasks that caches values in Redis."""

    def _use_redis_cache(func):

        @functools.wraps(func)
        def cached_func(self, *args, **kwargs):
            logger = get_task_logger(__name__)

            key = self.build_cache_key(func.__name__, args, kwargs)
            cached_value = self.redis.get(key)
            if cached_value is not None:
                logger.info(f'Using cached value: {key}')
                return json.loads(cached_value)

            value = func(self, *args, **kwargs)

            logger.info(f'Cacheing results: {key}')
            self.redis.set(key, json.dumps(value), ex=cache_ttl)

            return value

        return cached_func
    return _use_redis_cache


########################################################################################################################


app = Celery('mws', config_source=celeryconfig)


def route_tasks(name, args, kwargs, options, task=None, **kw):
    """Automatically create workers for queues when they are created."""
    queue_name = name.replace('.', '_')
    return {'queue': queue_name}


app.conf.task_routes = {
    'mws.*': route_tasks
}

if __name__ == '__main__':
    app.start()