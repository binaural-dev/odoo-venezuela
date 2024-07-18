from odoo import fields, models

import logging
_logger = logging


class AccountMove(models.Model):
    _inherit = "account.move"

    def get_reversed_entry(self):
        reversed_id = super().get_reversed_entry()
        if reversed_id:
            _logger.info(reversed_id)
            return reversed_id 

        invoice = self.invoice_line_ids.pos_order_line_ids.order_id.refunded_order_ids.account_move
        _logger.info(invoice)
        return self.reversed_entry_id
