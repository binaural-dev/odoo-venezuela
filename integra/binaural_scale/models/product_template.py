from odoo import models, fields, api, _
from odoo.exceptions import UserError


import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    plu_id = fields.Char(string="PLU ID")

    @api.model
    def set_barcode_products_with_plu(self):
        products = self.search(
            [
                ("plu_id", "!=", False),
                ("company_id", "in", [self.env.company.id,False]),
            ]
        )
        products.set_barcode_by_plu()

    def set_barcode_by_plu(self):
        code = "21"
        if len(self) > 0 and self[0].env.company.scan_barcode_scale_by_price:
            code = "23"
        for record in self:
            if record.plu_id:
                barcode = f"{code}{record.plu_id.zfill(5) or 00000}000000"
                new_barcode = record.env["barcode.nomenclature"].sanitize_ean(barcode)
                record.write({"barcode": new_barcode})
            if not record.plu_id:
                record.write({"barcode": False})

    @api.onchange("plu_id")
    def _unique_plu(self):
        product = self.env["product.template"].search(
            [
                ("plu_id", "=", self.plu_id),
                ("plu_id", "!=", False),
                ("company_id", "in", [self.env.company.id, False]),
            ]
        )
        if product:
            raise UserError(_("Este PLU ya existe en otro producto"))
        self.set_barcode_by_plu()

