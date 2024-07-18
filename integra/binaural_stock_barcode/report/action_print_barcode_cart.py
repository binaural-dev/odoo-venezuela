from odoo import models, api, _
from odoo.exceptions import ValidationError


class BinauralPaymentExtensionRetentionIvaVoucher(models.AbstractModel):
    _name = "report.binaural_stock_barcode.cart_print_barcode"

    @api.model
    def _get_report_values(self, docids, data=None):
        carts = self.env["stock.picking.cart"].browse(docids)

        carts_rows = []
        pages = []
        temp_record = self.env["stock.picking.cart"]
        temp_page = []

        for cart in carts:
            if len(temp_record) < 2:
                temp_record |= cart
                if len(temp_record) == 2:
                    carts_rows.append(temp_record)
                    temp_record = self.env["stock.picking.cart"]
                temp_page = carts_rows

            if not temp_record and len(carts_rows) > 6:
                pages.append(carts_rows)
                temp_page = []
                carts_rows = []

        if len(temp_record) == 1:
            carts_rows.append(temp_record)

        if len(temp_page) < 7:
            pages.append(carts_rows)

        return {
            "docids": docids,
            "docs": self.env["stock.picking.cart"].browse(docids),
            "pages": pages,
        }

