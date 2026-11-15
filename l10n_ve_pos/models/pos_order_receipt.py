from odoo import models


class PosOrderReceipt(models.AbstractModel):
    """Python mirror of ``static/src/overrides/utils/generate_printer_data.js``:
    the receipt data the server builds (self-order, backend reprints) carries
    what the cashier receipt carries."""

    _inherit = "pos.order.receipt"

    def _order_receipt_generate_taxe_data(self):
        res = super()._order_receipt_generate_taxe_data()
        foreign_currency = self.config_id.foreign_currency_id
        if foreign_currency:
            res["foreign_total_amount"] = self._order_receipt_format_currency(
                self.foreign_amount_total, foreign_currency
            )
        return res

    def _order_receipt_generate_line_data(self):
        lines = super()._order_receipt_generate_line_data()
        foreign_currency = self.config_id.foreign_currency_id
        display_price_incl = self.config_id.iface_tax_included == "total"
        for line, data in zip(self.lines, lines):
            data["aliquot_type"] = self._order_receipt_aliquot_type(line)
            data["foreign_price_subtotal_incl"] = (
                self._order_receipt_format_currency(
                    self._amount_to_foreign(
                        line.price_subtotal_incl if display_price_incl else line.price_subtotal
                    ),
                    foreign_currency,
                )
                if foreign_currency
                else False
            )
        return lines

    def _order_receipt_aliquot_type(self, line):
        """"(E)" when the line has no tax or its first tax is 0%, else "(G)":
        ``get_aliquot_type`` of the point of sale."""
        taxes = line.tax_ids or line.product_id.with_company(self.company_id).taxes_id
        if not taxes or taxes[0].amount == 0:
            return "(E)"
        return "(G)"
