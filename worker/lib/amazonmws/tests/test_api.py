import re
import pytest
import unittest.mock as mock
from amazonmws.api import *


TEST_CREDENTIALS = {
    'access_key': '123456789',
    'secret_key': '123456789abcdefghijklmnopqrstuvwxyz',
    'seller_id': 'a1b2c3d4e5f6'
}


@pytest.fixture()
def amzcall_object():
    return AmzCall(**TEST_CREDENTIALS)


########################################################################################################################


@pytest.mark.parametrize('access_key', [TEST_CREDENTIALS['access_key'], None])
@pytest.mark.parametrize('secret_key', [TEST_CREDENTIALS['secret_key'], None])
@pytest.mark.parametrize('seller_id', [TEST_CREDENTIALS['seller_id'], None])
@pytest.mark.parametrize('auth_token', ['test_token', None])
def test_init_credentials(access_key, secret_key, seller_id, auth_token):
    """Test the AmzCall.__init__() method with different credentials."""
    if None in (access_key, secret_key, seller_id):
        with pytest.raises(ValueError):
            test_object = AmzCall(access_key, secret_key, seller_id)
        return

    kwargs = {'auth_token': auth_token} if auth_token is not None else {}
    test_object = AmzCall(access_key, secret_key, seller_id, **kwargs)

    assert test_object._access_key == access_key
    assert test_object._secret_key == secret_key
    assert test_object._account_id == seller_id

    if auth_token:
        assert test_object._auth_token == auth_token


@pytest.mark.parametrize('domain', [*list(MWS_DOMAINS.keys()), 'xx', 'some domain', None])
def test_init_regions(domain):
    """Test different values of the region parameter."""

    if domain in MWS_DOMAINS:
        test_object = AmzCall(**TEST_CREDENTIALS, domain=domain)
        assert test_object._domain == MWS_DOMAINS[domain]

    elif domain is None:
        test_object = AmzCall(**TEST_CREDENTIALS)
        assert test_object._domain in MWS_DOMAINS.values()

    elif len(domain) == 2:  # 2-letter designation NOT in MWS_DOMAINS
        with pytest.raises(ValueError):
            test_object = AmzCall(**TEST_CREDENTIALS, domain=domain)

    else:
        test_object = AmzCall(**TEST_CREDENTIALS, domain=domain)
        assert test_object._domain == domain


@pytest.mark.parametrize('default_market', [*list(MARKETID.keys()), 'xx', 'some market', None])
def test_init_default_market(default_market):
    """Test different values for the default_market parameter."""

    if default_market in MARKETID:
        test_object = AmzCall(**TEST_CREDENTIALS, default_market=default_market)
        assert test_object._default_market == MARKETID[default_market]

    elif default_market is None:
        test_object = AmzCall(**TEST_CREDENTIALS)
        assert test_object._default_market in MARKETID.values()

    elif len(default_market) == 2:  # 2-letter designation NOT in MARKETID
        with pytest.raises(ValueError):
            test_object = AmzCall(**TEST_CREDENTIALS, default_market=default_market)

    else:
        test_object = AmzCall(**TEST_CREDENTIALS, default_market=default_market)
        assert test_object._default_market == default_market


@pytest.mark.parametrize('make_request', [lambda x: x, 'foo', None])
def test_init_make_request(make_request):
    """Test different values for the make_request parameter."""

    if callable(make_request):
        test_object = AmzCall(**TEST_CREDENTIALS, make_request=make_request)
        assert test_object.make_request is make_request

    elif make_request is None:
        test_object = AmzCall(**TEST_CREDENTIALS)
        assert test_object.make_request is print

    else:
        with pytest.raises(TypeError):
            test_object = AmzCall(**TEST_CREDENTIALS, make_request=make_request)


@pytest.mark.parametrize('root', ['SomeList', 'ListSome'])
def test_enumerate_param_general(root):
    """Test the general behavior of the enumerate_param() method."""

    results = AmzCall.enumerate_param(root, ['one', 'two', 'three'])

    assert results == {
        root + '.Some.1': 'one',
        root + '.Some.2': 'two',
        root + '.Some.3': 'three'
    }


def test_enumerate_param_marketids():
    """Test the enumerate_param() method in the special case where root='MarketplaceId'."""

    results = AmzCall.enumerate_param('MarketplaceId', ['one', 'two', 'three'])

    assert results == {
        'MarketplaceId.Id.1': 'one',
        'MarketplaceId.Id.2': 'two',
        'MarketplaceId.Id.3': 'three'
    }


@mock.patch('amazonmws.api.gmtime')
def test_build_request_params(mock_gmtime, amzcall_object):
    """Test the build_request_params() method."""

    mock_gmtime.return_value = (2017, 12, 11, 6, 27, 4, 0, 345, 0)

    response = amzcall_object.build_request_params(
        'action name',
        param1='value',
        param2=1234,
        ParamList=['one', 'two', 'three'],
        ListParam=['one', 'two', 'three']
    )

    expected_params = {
        'AWSAccessKeyId': TEST_CREDENTIALS['access_key'],
        AmzCall.ACTION_TYPE: 'action name',
        AmzCall.ACCOUNT_TYPE: TEST_CREDENTIALS['seller_id'],
        'SignatureMethod': 'HmacSHA256',
        'SignatureVersion': '2',
        'Version': AmzCall.VERSION,
        'Timestamp': strftime('%Y-%m-%dT%H:%M:%SZ', mock_gmtime.return_value),
        'param1': 'value',
        'param2': 1234,
        'ParamList.Param.1': 'one',
        'ParamList.Param.2': 'two',
        'ParamList.Param.3': 'three',
        'ListParam.Param.1': 'one',
        'ListParam.Param.2': 'two',
        'ListParam.Param.3': 'three'
    }

    if amzcall_object._auth_token:
        expected_params['MWSAuthToken'] = amzcall_object._auth_token

    quoted_params = {key:
        urllib.parse.quote(
            str(value),
            safe='-_.~',
            encoding='utf-8'
        ) for key, value in expected_params.items()
    }

    expected_string = '&'.join((f'{key}={quoted_params[key]}' for key in sorted(quoted_params)))

    assert response == expected_string


@mock.patch('amazonmws.api.gmtime')
def test_build_request_url(mock_gmtime):
    """Test the build_request_url() method. This test uses the Products API, and checks the built URL
    against one produced by MWS Scratchpad."""

    mock_gmtime.return_value = (2017, 12, 11, 6, 44, 20, 0, 345, 0)
    api = Products(**TEST_CREDENTIALS)

    method = 'POST'
    action = 'ListMatchingProducts'
    params = {
        'MarketplaceId': 'ATVPDKIKX0DER',
        'Query': 'look for this'
    }
    expected_signature = urllib.parse.quote('Vw2xTz0g0x92floBpKuAfOddDz5MUk4u8xKY7+p8tGA=', safe='')
    param_string = api.build_request_params(action, **params)

    request_url = api.build_request_url(method=method, action=action, **params)

    assert re.search(r'Signature=(.*)', request_url)[1] == expected_signature
    assert request_url == f'https://{api._domain}{api.URI}?{param_string}&Signature={expected_signature}'


def test_getattr(amzcall_object):
    """Test the getattr() method."""
    amzcall_object._do_api_call = mock.Mock()
    amzcall_object.DoSomething()

    amzcall_object._do_api_call.assert_called_with('DoSomething')
