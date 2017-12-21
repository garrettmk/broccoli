from .common import *


########################################################################################################################


@app.task(base=MWSTask, bind=True)
class GetServiceStatus(MWSTask):
    cache_ttl = 60 * 5


@app.task(base=MWSTask, bind=True)
class ListMatchingProducts(MWSTask):
    cache_ttl = 60 * 60


@app.task(base=MWSTask, bind=True)
class GetMyFeesEstimate(MWSTask):
    cache_ttl = 60 * 30
    restore_rate_adjust = 5
