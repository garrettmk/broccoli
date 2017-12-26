import collections
from celery import chain, group, chord
from celery.utils.log import get_task_logger
from bson import ObjectId
from .common import *
from parsed.products import *
from parsed.product_adv import *


logger = get_task_logger(__name__)


########################################################################################################################


@app.task(base=OpsTask, bind=True)
def find_amazon_matches(self, product_id, brand=None, model=None):
    """Find matching products in Amazon's catalog, import them, and create corresponding opportunities."""

    if None not in [brand, model]:
        query_string = f'{brand} {model}'
    else:
        raise NotImplementedError

    matches = ListMatchingProducts(query=query_string)

    amz_id = self.get_or_create_vendor('Amazon')
    collection = self.db.products
    for match in matches:
        # Insert/update the Amazon product
        match['vendor'] = amz_id
        match = collection.find_one_and_update(
            filter={
                'vendor': amz_id,
                'sku': match['sku']
            },
            update={
                '$set': {**match}
            },
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER
        )

        # Insert/update the opportunity relationship
        match_id = match['_id']
        opportunity = {
            'market_listing': match_id,
            'supplier_listing': product_id
        }
        opportunity = collection.find_one_and_update(
            filter={**opportunity},
            update={
                '$set': {**opportunity}
            },
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER
        )

        # Follow-up tasks:
        asin = match['sku']

        chain(
            chord(
                ItemLookup.s(asin),
                GetCompetitivePricingForASIN.s(asin)
            )(update_amazon_listing.s(match_id)),
            GetMyFeesEstimate.s(),
            update_amazon_listing.s(match_id),
            update_opportunities.s()
        ).apply_async()

        #   update_opportunity - calculate profit info with newly updated information, also recalculates the similarity score


@app.task(base=OpsTask, bind=True)
def update_amazon_listing(self, data, product_id):
    """Updates a product using various sources of data."""
    collection = self.db.products

    product_id = ObjectId(product_id)
    product = collection.find_one({'_id': product_id}, projection={'sku': 1})

    try: product_asin = product['sku']
    except AttributeError: raise ValueError(f'Invalid product id: {product_id}')

    # Separate the data sources into API call results and raw updates
    if not isinstance(data, collections.Sequence):
        data = [data]

    api_calls = [source for source in data if 'api_call' in source]
    raw_updates = [source for source in data if source not in api_calls]

    # Process API calls first
    for api_call in api_calls:
        call_type = api_call['api_call']

        if call_type == 'ItemLookup':
            try:
                product.update(api_call['results'][product_asin])
            except KeyError:
                logger.debug(f"API call {call_type} does not contain results for {product_asin}, ignoring...")

        elif call_type == 'GetCompetitivePricingForASIN':
            try:
                landed_price = api_call['results'][product_asin].get('landed_price', None)
                listing_price = api_call['results'][product_asin].get('listing_price', None)
                shipping = api_call['results'][product_asin].get('shipping', None)

                product['price'] = landed_price if landed_price is not None else listing_price + shipping
                product['offers'] = api_call['results'][product_asin].get('offers', None)
            except KeyError:
                logger.debug(f"API call {call_type} does not contain results for {product_asin}, ignoring...")

        elif call_type == 'GetMyFeesEstimate':
            try:
                product['price'] = api_call['results'][product_asin]['price']
                product['market_fees'] = api_call['results'][product_asin]['total_fees']
            except KeyError:
                logger.debug(f"API call {call_type} does not contain results for {product_asin}, ignoring...")
                continue

        else:
            raise ValueError(f"Unrecognized API call: {call_type}")

    # Process raw updates
    for raw_data in raw_updates:
        product.update(raw_data)

    # Write to the DB
    collection.find_one_and_update(
        filter={'_id': product_id},
        update={'$set': {**product}},
    )

    return product_id







