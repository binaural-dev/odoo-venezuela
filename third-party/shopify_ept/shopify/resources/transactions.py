from ..base import ShopifyResource
from .. import mixins


class Transactions(ShopifyResource, mixins.Metafields):
    _prefix_source = "/shopify_payments/balance/"
