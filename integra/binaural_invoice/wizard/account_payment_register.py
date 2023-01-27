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


    def _get_rate_from_invoice(self):
        """
        This method is used to get the foreign currency rate from the invoice

        Returns
        -------
        type = float
            The foreign currency rate of the invoice

        """
        for rec in self:
            rec.foreign_currency_rate = rec.line_ids.move_id.tax

    @api.depends("payment_date")
    def _compute_foreign_currency_rate(self):
        """
        This method is used to get the foreign currency rate from the currency rate table if changed the payment date

        Returns
        -------
        type = float
            The foreign currency rate of the currency rate table or the invoice


        """
        current_currency = self.env.company.currency_id.id
        foreign_currency = self.env["res.currency"].search([("active", "=", True)])
        for currency in foreign_currency:
            if currency.id != current_currency:
                for tax in currency.rate_ids:
                    if current_currency == 2:
                        if tax.name == self.payment_date:
                            self.foreign_currency_rate = tax.company_rate
                            break
                        self._get_rate_from_invoice()
                    else:
                        if tax.name == self.payment_date:

                            self.foreign_currency_rate = tax.inverse_company_rate
                            break
                        self._get_rate_from_invoice()
        
            




            
            
