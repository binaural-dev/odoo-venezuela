from collections import defaultdict

from odoo import api, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _check_ensure_one_ciu_on_ciu_ids(self):
        return

    @api.constrains("ciu_ids")
    def _check_one_ciu_per_municipality(self):
        ciu_per_municipality_count = defaultdict(int)
        for product in self:
            for ciu in product.ciu_ids:
                ciu_per_municipality_count[ciu.municipality_id.id] += 1
            if (
                any(ciu_count > 1 for ciu_count in ciu_per_municipality_count.values())
                and not self.env.company.use_subsidiary_with_multiple_municipalities
            ):
                raise ValidationError(
                    _("The product cannot have more than one CIU for the same municipality")
                )
