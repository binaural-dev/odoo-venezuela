from ..base import ShopifyResource
from .. import mixins


class Page(ShopifyResource, mixins.Metafields, mixins.Events):
    pass
