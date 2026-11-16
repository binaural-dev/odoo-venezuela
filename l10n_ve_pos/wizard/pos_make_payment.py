from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class PosMakePayment(models.TransientModel):
    _inherit = "pos.make.payment"

    def check(self):
        """Misma regla que la pantalla de pago del PdV (``payment_screen.js``,
        ``addNewPaymentLine``): un método en una tercera moneda
        (``tender_currency_id``) no se usa sin la tasa del día de esa moneda.
        Sin ella, ``pos.order._get_payment_tender_amount`` daría 0 y el pago
        quedaría con 0 € en el cajón y en el cruce."""
        self.ensure_one()
        self._check_tender_currency_rate()
        return super().check()

    def _check_tender_currency_rate(self):
        method = self.payment_method_id
        currency = method.tender_currency_id
        if not currency or float_is_zero(
            self.amount, precision_rounding=self.config_id.currency_id.rounding
        ):
            return
        config = self.config_id
        main = config.currency_id
        if config._get_pos_conversion_rate(main, currency) and config._get_pos_conversion_rate(
            currency, main
        ):
            return
        raise UserError(_(
            "There is no exchange rate of the day for %(currency)s: the payment method "
            "%(method)s cannot be used. Load the rate and reload the Point of Sale data.",
            currency=currency.name,
            method=method.name,
        ))
