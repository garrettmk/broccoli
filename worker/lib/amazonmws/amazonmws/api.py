# -*- coding: utf-8 -*-

"""
:mod:`api` -- Implements the amazonmws API
------------------------------------------

.. module:: api

Contains the implementation of the API and a few extras.
"""


import hmac
import urllib

from base64 import b64encode
from functools import partial
from hashlib import sha256, md5
from time import strftime, gmtime


#: A dictionary of endpoints for the MWS API, keyed by country code.
MWS_DOMAINS = {
    'NA': 'mws.amazonservices.com',
    'EU': 'mws-eu.amazonservices.com',
    'IN': 'mws.amazonservices.in',
    'CN': 'mws.amazonservices.com.cn',
    'JP': 'mws.amazonservices.jp'
}

#: A dictionary of endpoints for the Product Advertising API, keyed by country code.
PA_ENDPOINT = {
    'BR': 'webservices.amazon.com.br',
    'CN': 'webservices.amazon.cn',
    'CA': 'webservices.amazon.ca',
    'DE': 'webservices.amazon.de',
    'ES': 'webservices.amazon.es',
    'FR': 'webservices.amazon.fr',
    'IN': 'webservices.amazon.in',
    'IT': 'webservices.amazon.it',
    'JP': 'webservices.amazon.co.jp',
    'MX': 'webservices.amazon.com.mx',
    'UK': 'webservices.amazon.co.uk',
    'US': 'webservices.amazon.com'
}

#: A dictionary of Amazon market IDs, keyed by country code.
MARKETID = {
    'CA': 'A2EUQ1WTGCTBG2',
    'MX': 'A1AM78C64UM0Y8',
    'US': 'ATVPDKIKX0DER',
    'DE': 'A1PA6795UKMFR9',
    'ES': 'A1RKKUPIHCS9HS',
    'FR': 'A13V1IB3VIYZZH',
    'IT': 'APJ6JRA9NG5V4',
    'UK': 'A1F83G8C2ARO7P',
    'IN': 'A21TJRUUN4KGV',
    'JP': 'A21TJRUUN4KGV',
    'CN': 'AAHKV2X7AFYLW'
}


class AmzCall:
    """Base class for API objects. Handles building and signing requests.
    """

    URI = '/'
    VERSION = '2009-01-01'
    ACCOUNT_TYPE = 'SellerId'
    ACTION_TYPE = 'Action'
    USER_AGENT = 'amazonmws/0.0.1 (Language=Python)'

    def __init__(self, access_key, secret_key, seller_id, auth_token=None, domain='NA', default_market='US', make_request=None):
        """Initialize the AmzCall object."""

        if None in (access_key, secret_key, seller_id):
            raise ValueError('access_key, secret_key, or seller_id can not be None.')

        if len(default_market) == 2 and default_market not in MARKETID:
            good_ids = ', '.join(MARKETID.keys())
            raise ValueError(f'Invalid market designation: {default_market}. Recognized values are {good_ids}.')

        if len(domain) == 2 and domain not in MWS_DOMAINS:
            raise ValueError(f'Invalid region: {domain}. Recognized values are {", ".join(MWS_DOMAINS.keys())}.')

        self._access_key = access_key
        self._secret_key = secret_key
        self._account_id = seller_id
        self._auth_token = auth_token
        self._domain = MWS_DOMAINS[domain] if len(domain) == 2 else domain
        self._default_market = MARKETID[default_market] if len(default_market) == 2 else default_market
        self.make_request = make_request or print

    @staticmethod
    def enumerate_param(root, values):
        """Formats a list of values into a parameter list acceptable to MWS."""
        if root == 'MarketplaceId':
            ptype = 'Id'
        else:
            ptype = root.replace('List', '')        # Ex: ASINList -> ASIN

        params = {}

        for num, val in enumerate(values, start=1):
            base = '{}.{}.{}'.format(root, ptype, num)
            if isinstance(val, dict):
                params.update({'{}.{}'.format(base, k):str(v) for k,v in val.items()})
            else:
                params.update({base:val})

        return params

    def build_request_params(self, action, **kwargs):
        """Return a dict populated with request parameters."""

        params = {
            'AWSAccessKeyId': self._access_key,
             self.ACTION_TYPE: action,
             self.ACCOUNT_TYPE: self._account_id,
             'SignatureMethod': 'HmacSHA256',
             'SignatureVersion': '2',
             'Timestamp': strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()),
             'Version': self.VERSION
        }

        if self._auth_token:
            params['MWSAuthToken'] = self._auth_token

        for k, v in kwargs.items():
            if k.endswith('List') or k.startswith('List'):
                params.update(self.enumerate_param(k, v))
            elif v:
                params.update({k: v})

        quoted_params = {key:
            urllib.parse.quote(
                str(value),
                safe='-_.~',
                encoding='utf-8'
            ) for key, value in params.items()
        }

        return '&'.join((f'{key}={quoted_params[key]}' for key in sorted(quoted_params)))

    def build_request_url(self, method, action, **kwargs):
        """Return a properly formatted and signed request URL based on the given parameters."""
        params = self.build_request_params(action, **kwargs)

        string_to_sign = '\n'.join((
            method.upper(),
            self._domain.lower(),
            self.URI, params
        ))

        # Create the signature
        signature = b64encode(
            hmac.new(
                self._secret_key.encode(), string_to_sign.encode(), sha256
            ).digest()
        )

        signature = urllib.parse.quote(signature.decode(), safe='')

        # Create the URL
        return f'https://{self._domain}{self.URI}?{params}&Signature={signature}'

    def __getattr__(self, name):
        return partial(self._do_api_call, name)

    def _do_api_call(self, operation, **kwargs):
        headers = {
            'User-Agent': self.USER_AGENT
        }

        # If body is provided, include an MD5 signature in the header
        body = kwargs.pop('body', None)
        if body:
            md = b64encode(
                md5(
                    body.encode()
                ).digest()
            ).strip(b'\n')

            headers.update({
                'Content-MD5': md,
                'Content-Type': 'text/xml'
            })

        url = self.build_request_url('POST', operation, **kwargs)

        return self._make_request(method='POST', url=url, data=body, headers=headers)

    @property
    def make_request(self):
        return self._make_request

    @make_request.setter
    def make_request(self, func):
        if not callable(func):
            raise TypeError('Expected callable object, got %s' % type(func))
        self._make_request = func


class Feeds(AmzCall):
    """Interface to the Feeds section of the MWS API."""
    URI = '/'
    VERSION = '2009-01-01'


class Finances(AmzCall):
    """Interface to the Finances section of the API."""
    URI = '/Finances/2015-05-01'
    VERSION = '2015-05-01'


class Products(AmzCall):
    """Interface to the Products section of the MWS API."""
    URI = '/Products/2011-10-01'
    VERSION = '2011-10-01'


class FulfillmentInboundShipment(AmzCall):
    """Interface to the Fulfillment Inbound Shipment section of the API."""
    URI = '/FulfillmentInboundShipment/2010-10-01'
    VERSION = '2010-10-01'


class FulfillmentInventory(AmzCall):
    """Interface to the Fulfillment Inventory section of the API."""
    URI = '/FulfillmentInventory/2010-10-01'
    VERSION = '2010-10-01'


class FulfillmentOutboundShipment(AmzCall):
    """Interface to the Fulfillment Outbound Shipment section of the API."""
    URI = '/FulfillmentOutboundShipment/2010-10-01'
    VERSION = '2010-10-01'


class MerchantFulfillment(AmzCall):
    """Interface to the Merchant Fulfillment section of the API."""
    URI = '/MerchantFulfillment/2015-06-01'
    VERSION = '2015-06-01'


class Orders(AmzCall):
    """Interface to the Orders section of the API."""
    URI = '/Orders/2013-09-01'
    VERSION = '2013-09-01'


class Products(AmzCall):
    """Interface to the Products section of the API."""
    URI = '/Products/2011-10-01'
    VERSION = '2011-10-01'


class Recommendations(AmzCall):
    """Interface to the Recommendations section of the API."""
    URI = '/Recommendations/2013-04-01'
    VERSION = '2013-04-01'


class Reports(AmzCall):
    """Interface to the Reports section of the API."""
    URI = '/'
    VERSION ='2009-01-01'


class Sellers(AmzCall):
    """Interface to the Sellers section of the API."""
    URI = '/Sellers'
    VERSION = '2011-07-01'


class Subscriptions(AmzCall):
    """Interface to the Subscriptions section of the API."""
    URI = '/Subscriptions/2013-07-01'
    VERSION = '2013-07-01'


class ProductAdvertising(AmzCall):
    """Interface to the Product Advertising API."""
    URI = '/onca/xml'
    VERSION = ''
    ACCOUNT_TYPE = 'AssociateTag'
    ACTION_TYPE = 'Operation'

    def __init__(self, access_key, secret_key, account_id, **kwargs):
        region = kwargs.pop('region', 'US')
        super(ProductAdvertising, self).__init__(access_key, secret_key, account_id, **kwargs)

        try:
            self._domain = PA_ENDPOINT[region]
        except KeyError:
            raise ValueError(f'Invalid region: {region}. Recognized values are {", ".join(PA_ENDPOINT.keys())}')

    def _api_call(self, operation, **kwargs):
        kwargs['Service'] = 'AWSECommerceService'
        headers = self.build_headers()
        url = self.build_request_url('GET', operation, **kwargs)

        return self._make_request('GET', url, headers=headers)