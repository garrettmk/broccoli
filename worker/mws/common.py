import hashlib
import json
import redis
import requests
import os
import time
import lib.amazonmws.amazonmws as amz_mws

from worker import app


########################################################################################################################


mws_priority_quotas = {
    0: {
        'GetServiceStatus': 1,
        'ListMatchingProducts': 1,
        'GetMyFeesEstimate': 1
    },
    1: {
        'GetServiceStatus': 1,
        'ListMatchingProducts': 5,
        'GetMyFeesEstimate': 5,
    },
    2: {
        'GetServiceStatus': 2,
        'ListMatchingProducts': 20,
        'GetMyFeesEstimate': 20
    }
}

mws_credentials = {
    'access_key': os.environ.get('MWS_ACCESS_KEY', 'test_access_key'),
    'secret_key': os.environ.get('MWS_SECRET_KEY', 'test_secret_key'),
    'seller_id': os.environ.get('MWS_SELLER_ID', 'test_account_id')
}


########################################################################################################################


class MWSTask(app.Task):
    """Common behaviors for all MWS API calls."""
    cache_ttl = 30
    default_retry_delay = 5
    soft_time_limit = 30
    pending_expires = 200
    restore_rate_adjust = 0

    @staticmethod
    def _use_requests(method, **kwargs):
        """Adapter function that lets the amazonmws library use requests."""
        if method == 'POST':
            return requests.post(**kwargs)
        elif method == 'GET':
            return requests.get(**kwargs)
        else:
            raise ValueError('Unsupported HTTP method: ' + method)

    def __init__(self):
        """Initialize the task object."""
        # Set up database connections here
        self.api = None
        self.redis = redis.from_url(os.environ['REDIS_URL'])
        #self.mongodb = pymongo.MongoClient(os.environ['MONGODB_URI'])
        self._credentials = {
            'access_key': os.environ.get('MWS_ACCESS_KEY', 'test_access_key'),
            'secret_key': os.environ.get('MWS_SECRET_KEY', 'test_secret_key'),
            'seller_id': os.environ.get('MWS_SELLER_ID', 'test_account_id')
        }

        self._cache_key = None
        self._cached_value = None
        self._action_name = None
        self._api_name = None

    def __call__(self, *args, **kwargs):
        """Perform the API call."""
        self._api_name, self._action_name = self.name.split('.')[-2:]
        self._api_name = self._api_name.capitalize()

        # Check the cache
        self.build_cache_key(*args, **kwargs)
        self.get_cached_value()

        if self._cached_value is not None:
            self.run = self._return_cached_value
        else:
            self.run = self._make_api_call

        return super().__call__(*args, **kwargs)

    def _return_cached_value(self, *args, **kwargs):
        return self._cached_value

    def _make_api_call(self, *args, **kwargs):
        """Make the api call, save the value to the cache, and update usage statistics."""
        priority = kwargs.pop('priority', 0)

        self.load_api()
        self.load_throttle_limits(priority)

        self.start_api_call()
        print(f'Wait time: {self.api.calculate_wait(self._action_name)}')
        try:
            return_value = getattr(self.api, self._action_name)(*args, **kwargs).text
        except Exception as e:
            self.end_api_call()
            raise e

        self.end_api_call()
        self.save_to_cache(return_value)
        return return_value

    def load_throttle_limits(self, priority):
        """Load custom throttle limits based on a task's name and priority."""
        priority_ceil = max(mws_priority_quotas)

        try:
            priority = min(int(priority), priority_ceil)
        except TypeError:
            print(f'Invalid priority value: {priority}\nUsing default priority (0)')
            priority = 0

        try:
            self.api.limits[self._action_name]['quota_max'] = mws_priority_quotas[priority][self._action_name]
            print(f'Throttle limits: quota_max={mws_priority_quotas[priority][self._action_name]}')
        except KeyError:
            pass

        self.api.limits[self._action_name]['restore_rate'] += self.restore_rate_adjust

    def start_api_call(self):
        """Load usage data into the API throttler, and increment the pending counter for this operation."""
        usage_key = self.name + '_usage'
        pending_key = self.name + '_pending'

        pipe = self.redis.pipeline()
        pipe.mget(usage_key, pending_key)
        pipe.incr(pending_key)
        pipe.expire(pending_key, self.pending_expires)
        values = pipe.execute()[0]

        try:
            usage = json.loads(values[0].decode().replace('\'', '\"'))
        except Exception as e:
            print(e, repr(e))
            usage = {'quota_level': 0}

        try:
            pending = int(values[1])
        except TypeError:
            pending = 0

        if pending:
            usage['quota_level'] += pending
            usage['last_request'] = time.time()

        self.api._usage[self._action_name] = usage
        print(f'{usage_key}: {usage}, {pending_key}: {pending}')

    def end_api_call(self):
        """Update the usage stats in the cache."""
        usage = self.api._usage[self._action_name]
        usage_key = self.name + '_usage'
        pending_key = self.name + '_pending'

        pipe = self.redis.pipeline()
        pipe.set(usage_key, usage)
        pipe.decr(pending_key)
        pipe.expire(pending_key, self.pending_expires)
        pipe.execute()

    def load_api(self):
        """Loads the correct API object from amz_mws, based on the module name of the current task."""
        self.api = amz_mws.Throttler(
            getattr(amz_mws, self._api_name)(
                **self._credentials,
                make_request=self._use_requests
            )
        )

    def build_cache_key(self, *args, **kwargs):
        """Build a key to store/retrieve cache values in redis. The key signature is build from the class name and
        the call signature."""
        if not self.cache_ttl:
            self._cache_key = None
        else:
            kwargs.pop('priority', None)

            sig = hashlib.md5(
                json.dumps({'args': args, 'kwargs': kwargs}).encode()
            ).hexdigest()

            self._cache_key = f'{self.name}_{sig}'

    def get_cached_value(self):
        """Return the value in the cache corresponding to the given args and kwargs, or None."""
        if not self.cache_ttl or not self.redis.exists(self._cache_key):
            self._cached_value = None
        else:
            self._cached_value = self.redis.get(self._cache_key).decode()

        return self._cached_value

    def save_to_cache(self, value):
        """Save the value to the cache."""
        if self.cache_ttl:
            self.redis.set(self._cache_key, value, ex=self.cache_ttl)
