from odoo import _, api, models
from odoo.exceptions import UserError


class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.model
    def _load_pos_data_read(self, records, config):
        """Odoo 19 loader contract: enrich each category with its parent
        resolved into a full dict (matches the legacy Odoo 17 contract).

        Odoo 19 returns many2one fields as a bare ``int`` when ``read`` is
        called with ``load=False``; this override normalizes the access.
        """
        res = super()._load_pos_data_read(records, config) or []
        category_by_id = {category['id']: category for category in res}

        for category in res:
            parent_id = category.get('parent_id')
            if isinstance(parent_id, (list, tuple)):
                parent_id = parent_id[0] if parent_id else False
            if parent_id:
                try:
                    category['parent'] = category_by_id[parent_id]
                except KeyError as e:
                    raise UserError(
                        _(
                            "The category %s does not belong to this company.",
                            category.get('name'),
                        )
                    ) from e
            else:
                category['parent'] = None

        return res
