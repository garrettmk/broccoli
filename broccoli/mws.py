import os
import re
import requests
import lib.amazonmws.amazonmws as mws
from lxml import etree
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


@app.task(rate_limit='12/h')
def GetServiceStatus(service):
    """Return the status of the given service."""
    result = apis[service].GetServiceStatus()

    xml = remove_namespaces(result.text)
    tree = etree.fromstring(xml)

    return tree.xpath('.//Status')[0].text
