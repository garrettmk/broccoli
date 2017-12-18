# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html
import os
import redis
import rq


class BroccoliPipeline:

    def __init__(self):
        self._redis = None
        self._queue = None

    def open_spider(self, spider):
        self._redis = redis.from_url(
            os.environ.get('REDIS_URL')
        )
        self._queue = rq.Queue(
            name='default',
            connection=self._redis
        )

    def close_spider(self, spider):
        self._redis = None

    def process_item(self, item, spider):
        vendor = spider.human_name
        item_data = dict(item)
        item_data.update(vendor=vendor)

        self._queue.enqueue(
            'spiders.clean_and_import',
            args=[item_data]
        )

        return item


