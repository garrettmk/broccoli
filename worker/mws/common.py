import functools
import hashlib
import json
import re
import requests
import os
import lib.amazonmws.amazonmws as amz_mws
from lxml import etree

from ..worker import app


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

mws_credentials = {
    'access_key': os.environ.get('MWS_ACCESS_KEY', 'test_access_key'),
    'secret_key': os.environ.get('MWS_SECRET_KEY', 'test_secret_key'),
    'seller_id': os.environ.get('MWS_SELLER_ID', 'test_account_id')
}


########################################################################################################################

#
# class AmzXmlResponse:
#     """A utility class for dealing with Amazon's XML responses."""
#
#     def __init__(self, xml=None):
#         self._xml = None
#         self.tree = None
#
#         self.xml = xml
#
#     @property
#     def xml(self):
#         return self._xml
#
#     @xml.setter
#     def xml(self, xml):
#         """Perform automatic etree parsing."""
#         self._xml, self.tree = None, None
#
#         if xml is not None:
#             self._xml = self.remove_namespaces(xml)
#             self.tree = etree.fromstring(self._xml)
#
#     @staticmethod
#     def remove_namespaces(xml):
#         """Remove all traces of namespaces from the given XML string."""
#         re_ns_decl = re.compile(r' xmlns(:\w*)?="[^"]*"', re.IGNORECASE)
#         re_ns_open = re.compile(r'<\w+:')
#         re_ns_close = re.compile(r'/\w+:')
#
#         response = re_ns_decl.sub('', xml)  # Remove namespace declarations
#         response = re_ns_open.sub('<', response)  # Remove namespaces in opening tags
#         response = re_ns_close.sub('/', response)  # Remove namespaces in closing tags
#         return response
#
#     def xpath_get(self, path, root_tag=None, _type=str, default=None):
#         """Utility method for getting data values from XPath selectors."""
#         tag = root_tag if root_tag is not None else self.tree
#         try:
#             data = tag.xpath(path)[0].text
#             if _type is str and data is None:
#                 raise TypeError
#             else:
#                 return _type(data)
#         except (IndexError, ValueError, TypeError):
#             return default
#
#     @property
#     def error_code(self):
#         """Holds the error code if the response was an error, otherwise None."""
#         if self.tree is None:
#             return None
#
#         return self.xpath_get('/ErrorResponse/Error/Code')
#
#     @property
#     def error_message(self):
#         """Holds the error message if the response was an error, otherwise None."""
#         if self.tree is None:
#             return None
#
#         return self.xpath_get('/ErrorResponse/Error/Message')
#
#     @property
#     def request_id(self):
#         """Returns the RequestID parameter."""
#         if self.tree is None:
#             return None
#
#         return self.xpath_get('//RequestID')
#
#     def error_as_json(self):
#         """Formats an error response as a simple JSON object."""
#         return {
#             'error': {
#                 'code': self.error_code,
#                 'message': self.error_message,
#                 'request_id': self.request_id
#             }
#         }


################################################################################################################################################################################################################################################


def _use_requests(method, **kwargs):
    """Adapter function that lets the amazonmws library use requests."""
    if method == 'POST':
        return requests.post(**kwargs)
    elif method == 'GET':
        return requests.get(**kwargs)
    else:
        raise ValueError('Unsupported HTTP method: ' + method)


def build_cache_key(full_name, args, kwargs):
    """Build a cache key from the given action and call signature."""
    sig = hashlib.md5(
        json.dumps({'args': args, 'kwargs': kwargs}).encode()
    ).hexdigest()

    return full_name + sig


def update_limits(throttler, priority):
    """Load priority-based throttling limits into the throttler object."""
    priority_ceil = max(mws_priority_quotas)
    try:
        priority = min(int(priority), priority_ceil)
    except TypeError:
        print(f'Invalid priority value: {priority}\nUsing default priority (0)')
        priority = 0

    quota_maxes = mws_priority_quotas[priority]

    for action, quota in quota_maxes.items():
        throttler.limits[action]['quota_max'] = quota


def load_usage(throttler, full_name):
    """Load the usage data for a given action."""
    db = rq.get_current_connection()
    try:
        usage = json.loads(
            db.get(full_name + '_usage').decode().replace('\'', '\"')
        )
    except (TypeError, AttributeError):
        return

    action = full_name.split('.')[-1]
    throttler._usage[action] = usage


def save_usage(throttler, full_name):
    """Save the usage data for a particular action in the redis cache."""
    db = rq.get_current_connection()
    action = full_name.split('.')[-1]
    db.set(full_name + '_usage', throttler._usage[action])


# def use_redis_cache(cache_ttl):
#     """Decorator for MWS tasks that caches values in Redis."""
#
#     def _use_redis_cache(func):
#
#         @functools.wraps(func)
#         def cached_func(self, *args, **kwargs):
#             key = self.build_cache_key(func.__name__, args, kwargs)
#             cached_value = self.redis.get(key)
#             if cached_value is not None:
#                 print(f'Using cached value: {key}')
#                 return json.loads(cached_value)
#
#             value = func(self, *args, **kwargs)
#
#             print(f'Cacheing results: {key}')
#             self.redis.set(key, json.dumps(value), ex=cache_ttl)
#
#             return value
#
#         return cached_func
#     return _use_redis_cache


def mwstask(*args, cache_ttl=None, **kwargs):
    """Custom decorator that provides common behaviors for MWS tasks."""
    def _mwstask(func):
        @functools.wraps(func)
        def __mwstask(*__args, **__kwargs):
            full_name = func.__module__ + '.' + func.__name__
            print(f'full_name: {full_name}')

            # Check the cache here
            if cache_ttl is not None:
                r = rq.get_current_connection()
                key = build_cache_key(full_name, __args, __kwargs)
                cached_value = r.get(key)
                if cached_value is not None:
                    print(f'Using cached value {key}')
                    return json.loads(cached_value)

            # Load up the API object
            api = amz_mws.Throttler(
                api=getattr(amz_mws, full_name.split('.')[-2].capitalize())(
                    **mws_credentials,
                    make_request=_use_requests
                )
            )

            update_limits(api, __kwargs.pop('priority', 0))
            load_usage(api, full_name)

            value = func(api, *__args, **__kwargs)

            save_usage(api, full_name)

            if cache_ttl is not None:
                r.set(key, json.dumps(value), ex=cache_ttl)

            return value

        return __mwstask
    return _mwstask


########################################################################################################################


class MWSTask(app.Task):
    """Common behaviors for all MWS API calls."""

    def __init__(self):
        """Initialize the task object."""
        # Set up database connections here

    def __call__(self, *args, **kwargs):
        """Perform the API call."""
        # Check the cache
        # If cached_value exists, set self.run() to return the cached value
        # Else, set self.run() to