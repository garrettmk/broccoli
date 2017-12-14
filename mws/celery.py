import os
import re
import requests
import lib.amazonmws.amazonmws as amz_mws
from celery import Celery, Task
from lxml import etree


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
        pass

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
            'access_key': os.environ.get('MWS_ACCESS_KEY'),
            'secret_key': os.environ.get('MWS_SECRET_KEY'),
            'account_id': os.environ.get('MWS_ACCOUNT_ID')
        }

        # TODO: load usage information (for throttling) here

        return getattr(amz_mws, name)(**credentials, make_request=self._use_requests)


########################################################################################################################


app = Celery(
    'mws',
    broker=os.environ.get('CLOUDAMQP_URL', 'pyamqp://guest:guest@rabbit:5672'),
    backend='rpc://',
    include=[
        'mws.products'
    ]
)


# Do configuration (throttling limits?) here
# app.conf.update()

if __name__ == '__main__':
    app.start()