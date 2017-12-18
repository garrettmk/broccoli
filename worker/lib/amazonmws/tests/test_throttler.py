import pytest
import unittest.mock as mock
from amazonmws.throttler import Throttler, DEFAULT_LIMITS


@pytest.fixture(params=['under_quota', 'at_quota', 'over_quota'])
def usage(request):
    if request.param == 'under_quota':
        quota_level = DEFAULT_LIMITS['ListMatchingProducts']['quota_max'] - 5
    elif request.param == 'at_quota':
        quota_level = DEFAULT_LIMITS['ListMatchingProducts']['quota_max']
    else:
        quota_level = DEFAULT_LIMITS['ListMatchingProducts']['quota_max'] + 5

    return {
        'ListMatchingProducts': {
            'quota_level': quota_level,
            'last_request': 1000
        }
    }


@pytest.fixture()
def throttler(usage):
    thrott = Throttler(api=mock.Mock())
    thrott._usage = usage

    return thrott


########################################################################################################################


def test_init_defaults():
    """Check initialization defaults."""
    throttler = Throttler()
    assert throttler.api is None
    assert throttler.limits == DEFAULT_LIMITS


def test_init_override_defaults():
    """Check that parameters to __init__() correctly override their default values."""
    mock_api = mock.Mock()
    new_limits = {}

    throttler = Throttler(api=mock_api, limits=new_limits)

    assert throttler.api is mock_api
    assert throttler.limits is new_limits


@mock.patch('amazonmws.throttler.time')
def test_restore_quota(mock_time, throttler):
    """Test the restore_quota() method."""

    quota_level = throttler._usage['ListMatchingProducts']['quota_level']

    # Simulate the passage of 27 seconds, which should result in 27 // 5 = 5 slots restored
    mock_time.return_value = 1027
    throttler.restore_quota('ListMatchingProducts')

    assert throttler._usage['ListMatchingProducts']['quota_level'] == quota_level - 5


@mock.patch('amazonmws.throttler.time')
def test_restore_quota_all(mock_time, throttler):
    """Test that restore_quota() correctly sets the quota to zero when enough time has passed."""
    mock_time.return_value = 10000000
    throttler.restore_quota('ListMatchingProducts')
    assert throttler._usage['ListMatchingProducts']['quota_level'] == 0


def test_restore_quota_no_limits(throttler):
    """Test the restore_quota() method on an action where no limits have been set."""
    usage = dict(throttler._usage)

    throttler.restore_quota('Unlimited')

    assert throttler._usage == usage


def test_restore_quota_no_usage(throttler):
    """Test the restore_quota() method when limits are defined, but there is no usage."""
    usage = dict(throttler._usage)

    throttler.restore_quota('GetServiceStatus')

    assert throttler._usage == usage


@mock.patch('amazonmws.throttler.time')
def test_calculate_wait(mock_time, throttler):
    """Test the calculate_wait() method."""
    mock_time.return_value = 1001
    quota_max = DEFAULT_LIMITS['ListMatchingProducts']['quota_max']
    restore_rate = DEFAULT_LIMITS['ListMatchingProducts']['restore_rate']
    quota_level = throttler._usage['ListMatchingProducts']['quota_level']

    wait = throttler.calculate_wait('ListMatchingProducts')

    if quota_level < quota_max:
        assert wait == 0
    elif quota_level == quota_max:
        assert wait == 4    # Simulating the passage of 1 sec -> 4 secs left to restore
    else:
        assert wait == (quota_level - quota_max + 1) * restore_rate - 1


def test_calculate_wait_no_limits(throttler):
    """Test the calculate_wait() method on an action with no defined limits."""
    wait = throttler.calculate_wait('Unlimited')
    assert wait == 0


def test_calculate_wait_no_usage(throttler):
    """Test the calculate_wait() method on an action with defined limits, but no usage."""
    wait = throttler.calculate_wait('GetServiceStatus')
    assert wait == 0


@mock.patch('amazonmws.throttler.time')
def test_add_to_quota(mock_time, throttler):
    """Test the add_to_quota() method."""
    mock_time.return_value = 1027
    quota_level = throttler._usage['ListMatchingProducts']['quota_level']

    throttler.add_to_quota('ListMatchingProducts')

    assert throttler._usage['ListMatchingProducts']['quota_level'] == quota_level + 1
    assert throttler._usage['ListMatchingProducts']['last_request'] == mock_time.return_value


@mock.patch('amazonmws.throttler.time')
def test_add_to_quota_no_usage(mock_time, throttler):
    """Test the add_to_quota() method on an action with defined limits, but no usage."""
    mock_time.return_value = 1027

    throttler.add_to_quota('GetServiceStatus')

    assert throttler._usage['GetServiceStatus']['quota_level'] == 1
    assert throttler._usage['GetServiceStatus']['last_request'] == mock_time.return_value


def test_add_to_quota_no_limits(throttler):
    """Test the add_to_quota() method on an action with no defined limits."""
    current_usage = dict(throttler._usage)

    throttler.add_to_quota('Unlimited')

    assert throttler._usage == current_usage


# @mock.patch('amazonmws.throttler.sleep')
# @mock.patch('amazonmws.throttler.time')
# def test_api_call(mock_time, mock_sleep, throttler):
#     """Test the api_call() method."""
#     mock_time.side_effect = 1001, 1001, 1003, 1004
#     quota_level = throttler._usage['ListMatchingProducts']['quota_level']
#     quota_max = DEFAULT_LIMITS['ListMatchingProducts']['quota_max']
#     restore_rate = DEFAULT_LIMITS['ListMatchingProducts']['restore_rate']
#
#     throttler.api_call('ListMatchingProducts')
#
#     if quota_level < quota_max:
#         mock_sleep.assert_called_with(0)
#     elif quota_level == quota_max:
#         mock_sleep.assert_called_with(restore_rate - 1)
#     else:
#         mock_sleep.assert_called_with((quota_level - quota_max + 1) * restore_rate - 1)





