**amazonmws** provides a Python interface to Amazon's `Merchant Web Services (MWS) <https://developer.amazonservices.com/gp/mws/docs.html>`_
and `Product Advertising (PA) <http://docs.aws.amazon.com/AWSECommerceService/latest/DG/Welcome.html>`_ APIs. It is
designed to use whatever networking library you prefer, making it ideal for both CLI and GUI applications.

Basic Usage
-----------

First, create an instance of the API you want to access, using your Amazon MWS or PA credentials:

    >>> import requests
    >>> import amazonmws as mws
    >>> api = mws.Products(your_access_id, your_secret_key, your_seller_id)
    >>> api.make_request = requests.request

Here, we have created an object to access the Products section of the MWS API, and we have told it to use
``requests.request`` to communicate with Amazon. We can now access different API calls as methods on this object:

    >>> result = api.GetServiceStatus()
    >>> result
    <Response [200]>

When you make an API call, the object builds and signs the request URL, along with any other parameters necessary to
make the request. It then calls the ``make_request`` function and returns the result. In this case, because we are using
``requests.request``, the return value is a ``requests.Response`` object. We can see the XML response from Amazon using
the result's ``text`` attribute:

    >>> from pprint import pprint
    >>> pprint(result.text)
    ('<?xml version="1.0"?>\n'
     '<GetServiceStatusResponse '
     'xmlns="http://mws.amazonservices.com/schema/Products/2011-10-01">\n'
     '  <GetServiceStatusResult>\n'
     '    <Status>GREEN</Status>\n'
     '    <Timestamp>2017-10-09T20:59:18.297Z</Timestamp>\n'
     '  </GetServiceStatusResult>\n'
     '  <ResponseMetadata>\n'
     '    <RequestId>3e8932c9-a95a-41a9-b56c-34e65672289b</RequestId>\n'
     '  </ResponseMetadata>\n'
     '</GetServiceStatusResponse>\n')

Parameters are specified using keyword arguments:

    >>> result = api.ListMatchingProducts(MarketplaceId='ATVPDKIKX0DER', Query='Turtles')

The Product Advertising (PA) API
--------------------------------

Currently, Amazon's Product Advertising API is similar enough to MWS that I was able to support it without much trouble.
This might change in the future, of course, but for now it can be accessed like so:

    >>> api = mws.ProductAdvertising(your_access_key, your_secret_key, your_associate_tag)

