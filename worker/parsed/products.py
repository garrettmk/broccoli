from .common import *
import mws.products as products
from lib.amazonmws.amazonmws import MARKETID


########################################################################################################################


@app.task
def GetServiceStatus(**kwargs):
    response = AmzXmlResponse(
        products.GetServiceStatus(**kwargs)
    )

    return response.xpath_get('.//Status')


@app.task
def ListMatchingProducts(query, marketplace_id=MARKETID['US'], query_context_id=None, **kwargs):
    """Perform a ListMatchingProducts request.

    Response format:
    {
        'api_call': 'ListMatchingProducts',
        'succeeded': True,
        'params': {},
        'errors': {},
        'results': {}
    }
    """
    # Allow two-letter abbreviations for MarketplaceId
    params = {
        'Query': query,
        'MarketplaceId': marketplace_id if len(marketplace_id) > 2 else MARKETID.get(marketplace_id, 'US')
    }

    if query_context_id is not None:
        params['QueryContextId'] = query_context_id

    response = AmzXmlResponse(
        products.ListMatchingProducts(**params, **kwargs)
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


@app.task
def GetMyFeesEstimate(asin, price, marketplace_id=MARKETID['US'], **kwargs):
    """Return the total fees estimate for a given ASIN and price."""
    # Allow two-letter marketplace abbreviations
    marketplace_id = marketplace_id if len(marketplace_id) > 2 else MARKETID.get(marketplace_id, 'US')

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
        products.GetMyFeesEstimate(**params, **kwargs)
    )

    if response.error_code:
        return response.error_as_json()

    return response.xpath_get('.//TotalFeesEstimate/Amount', _type=float)

@app.task
def GetCompetitivePricingForASIN(asin, marketplace_id='US', **kwargs):
    """Perform a GetCompetivePricingForASIN call and return the results as a simplified JSON dictionary."""
    marketplace_id = marketplace_id if len(marketplace_id) > 2 else MARKETID.get(marketplace_id, 'US')

    params = {
        'MarketplaceId': marketplace_id,
        'ASINList': [asin]
    }

    response = AmzXmlResponse(
        products.GetCompetitivePricingForASIN(**params, **kwargs)
    )

    results = {}
    for result_tag in response.tree.iterdescendants('GetCompetitivePricingForASINResult'):
        price = {}
        sku = result_tag.attrib.get('ASIN')

        # Check that the request succeeded.
        if result_tag.attrib.get('status') != 'Success':
            code = response.xpath_get('.//Error/Code', result_tag)
            message = response.xpath_get('.//Error/Message', result_tag)
            price['error'] = f'{code}: {message}'
            results[sku] = price
            continue

        for price_tag in result_tag.iterdescendants('CompetitivePrice'):
            if price_tag.attrib.get('condition') != 'New':
                continue

            price['listing_price'] = response.xpath_get('.//ListingPrice/Amount', price_tag, _type=float)
            price['shipping'] = response.xpath_get('.//Shipping/Amount', price_tag, _type=float)
            price['landed_price'] = response.xpath_get('.//LandedPrice/Amount', price_tag, _type=float)

        for count_tag in result_tag.iterdescendants('OfferListingCount'):
            if count_tag.attrib.get('condition') == 'New':
                price['offers'] = count_tag.text
        else:
            if 'offers' not in price:
                price['offers'] = 0

        results[sku] = price

    return results


