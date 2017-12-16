from .celery import *


########################################################################################################################


@app.task(bind=True, base=MWSTask)
@use_redis_cache(cache_ttl=300)
def GetServiceStatus(self):
    """Return the status of the given service."""
    response = AmzXmlResponse(
        self.products.GetServiceStatus().text
    )

    if response.error_code:
        return response.error_as_json()
    else:
        return response.xpath_get('.//Status')


@app.task(bind=True, base=MWSTask)
@use_redis_cache(cache_ttl=30)
def ListMatchingProducts(self, query, marketplace_id=amz_mws.MARKETID['US'], query_context_id=None):
    """Perform a ListMatchingProducts request."""
    # Allow two-letter abbreviations for MarketplaceId
    kwargs = {
        'Query': query,
        'MarketplaceId': marketplace_id if len(marketplace_id) > 2 else amz_mws.MARKETID.get(marketplace_id, 'US')
    }

    if query_context_id is not None:
        kwargs['QueryContextId'] = query_context_id

    response = AmzXmlResponse(
        self.products.ListMatchingProducts(**kwargs).text
    )

    if response.error_code:
        return response.error_as_json()

    results = []
    for tag in response.tree.iterdescendants('Product'):
        product = dict()
        product['sku'] = response.xpath_get('./Identifiers/MarketplaceASIN/ASIN', tag)
        product['brand'] = response.xpath_get('.//Brand', tag) \
                           or response.xpath_get('.//Manufacturer', tag) \
                           or response.xpath_get('.//Label', tag) \
                           or response.xpath_get('.//Publisher', tag) \
                           or response.xpath_get('.//Studio', tag)
        product['model'] = response.xpath_get('.//Model', tag) \
                           or response.xpath_get('.//PartNumber', tag)
        product['price'] = response.xpath_get('.//ListPrice/Amount', tag, _type=float)
        product['NumberOfItems'] = response.xpath_get('.//NumberOfItems', tag, _type=int)
        product['PackageQuantity'] = response.xpath_get('.//PackageQuantity', tag, _type=int)
        product['image_url'] = response.xpath_get('.//SmallImage/URL', tag)
        product['title'] = response.xpath_get('.//Title', tag)

        for rank_tag in tag.iterdescendants('SalesRank'):
            if not rank_tag.xpath('./ProductCategoryId')[0].text.isdigit():
                product['category'] = response.xpath_get('./ProductCategoryId', rank_tag)
                product['rank'] = response.xpath_get('./Rank', rank_tag, _type=int)
                break

        product['description'] = '\n'.join([t.text for t in tag.iterdescendants('Feature')]) or None

        results.append({k: v for k, v in product.items() if v is not None})

    return results


@app.task(bind=True, base=MWSTask)
@use_redis_cache(cache_ttl=30*60)
def GetMyFeesEstimate(self, asin, price, marketplace_id=amz_mws.MARKETID['US']):
    """Return the total fees estimate for a given ASIN and price."""
    # Allow two-letter marketplace abbreviations
    marketplace_id = marketplace_id if len(marketplace_id) > 2 else amz_mws.MARKETID.get(marketplace_id, 'US')

    params = {
        'FeesEstimateRequestList': [
            {
                'MarketplaceId': marketplace_id,
                'IdType': 'ASIN',
                'IdValue': asin,
                'IsAmazonFulfilled': 'true',
                'Identifier': 'request1',
                'PriceToEstimateFees.ListingPrice.CurrencyCode': 'USD',
                'PriceToEstimateFees.ListingPrice.Amount': price
            }
        ]
    }

    response = AmzXmlResponse(
        self.products.GetMyFeesEstimate(**params).text
    )

    if response.error_code:
        return response.error_as_json()

    return response.xpath_get('.//TotalFeesEstimate/Amount', _type=float)