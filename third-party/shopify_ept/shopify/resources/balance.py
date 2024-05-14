from ..base import ShopifyResource
from .. import mixins


class Balance(ShopifyResource, mixins.Metafields):
    _prefix_source = "/shopify_payments/"
    _singular = _plural = "balance"
