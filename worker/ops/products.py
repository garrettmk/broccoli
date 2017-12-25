from celery import chain
from bson import ObjectId
from .common import *
from parsed.products import *
from parsed.product_adv import *


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

        # Queue up tasks, in order:
        #   upate_amazon_listing - retrieve current information and pricing (not provided by ListMatchingProducts)
        #   update_opportunity - calculate profit info with newly updated information, also recalculates the similarity score


@app.task(base=OpsTask, bind=True)
def update_amazon_listing(product_id):
    """Uses various MWS and PA api calls to update the given product."""
    product_id = ObjectId(product_id)
    collection = self.db.products
    product = collection.find_one({'_id': product_id})
    if product in None:
        raise ValueError(f'Invalid product id: {product_id}')





