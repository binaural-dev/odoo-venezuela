from odoo import models, fields, api, _
from odoo.exceptions import UserError


import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    plu_id = fields.Char(string="PLU ID")

    @api.onchange("plu_id")
    def _unique_plu(self):
        product = self.env["product.template"].search(
            [
                ("plu_id", "=", self.plu_id),
                ("plu_id", "!=", False),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if product:
            raise UserError(_("Este PLU ya existe en otro producto"))
        if self.plu_id:
            barcode = f"21{self.plu_id.zfill(5) or 00000}000000"
            new_barcode = self.env["barcode.nomenclature"].sanitize_ean(barcode)
            self.write({"barcode": new_barcode})
        if not self.plu_id:
            self.write({"barcode": False})
