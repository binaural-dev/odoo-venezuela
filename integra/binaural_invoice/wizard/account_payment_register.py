from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default value of the foreign currency field

        Returns
        -------
        type = int
            The id of the foreign currency of the company

        """
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False
    
    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    foreign_currency_rate = fields.Float(
        help="Foreign Currency Rate",
        compute="_compute_foreign_currency_rate",
        digits="Tasa",
        tracking=True,
        readonly=False
    )

    @api.depends("payment_date")
    def _compute_foreign_currency_rate(self):
        for rec in self:
            if rec.line_ids.move_id.tax:
                rec.foreign_currency_rate = rec.line_ids.move_id.tax
            




            
            
