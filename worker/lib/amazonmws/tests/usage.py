from functools import partial
import amazonmws as mws


class FakeApi:
    def __getattr__(self, action):
        print(f'API call: {action}')
        return self.foo

    def foo(self, *args, **kwargs):
        pass


action = 'ListMatchingProducts'
throttler = mws.Throttler(FakeApi())

for i in range(40):
    print(throttler._usage.get(action, {}))
    getattr(throttler, action)()