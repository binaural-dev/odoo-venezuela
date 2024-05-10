import logging
from odoo import models
from odoo.tools.float_utils import float_round, float_is_zero

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("is_change")
        res["search_params"]["fields"].append("is_payment_p2c")
        res["search_params"]["fields"].append("is_payment_pdv")
        return res

    def _loader_params_res_company(self):
        res = super()._loader_params_res_company()
        res["search_params"]["fields"].append("url_megasoft")
        res["search_params"]["fields"].append("port_megasoft")
        return res

    def get_total_payments(self):
        pos_payments = self.env["pos.payment"].search([("session_id", "=", self.id)])

        def is_change(payment):
            if payment.amount > 0 and payment.pos_order_id.amount_paid > 0:
                return False
            if payment.amount < 0 and payment.pos_order_id.amount_paid < 0:
                return False
            return True

        pos_payments = pos_payments.filtered(lambda payment: not is_change(payment))

        payments = pos_payments.filtered(
            lambda payment: bool(payment.pos_order_id.fiscal_machine)
            and bool(payment.payment_method_id.is_payment_pdv)
            and payment.amount > 0
        )

        refund_payments = pos_payments - payments

        if self.env.company.currency_id == self.env.ref("base.VEF"):
            return {
                "payments": "{0:.2f}".format(
                    float_round(
                        sum(payments.mapped("amount")),
                        precision_digits=self.env.company.currency_id.decimal_places,
                    )
                ),
                "refund_payments": "{0:.2f}".format(
                    float_round(
                        sum(refund_payments.mapped("amount")),
                        precision_digits=self.env.company.currency_id.decimal_places,
                    )
                ),
                "total": "{0:.2f}".format(
                    float_round(
                        sum(pos_payments.mapped("amount")),
                        precision_digits=self.env.company.currency_id.decimal_places,
                    )
                ),
            }
        else:
            return {
                "payments": "{0:.2f}".format(
                    float_round(
                        sum(payments.mapped("foreign_amount")),
                        precision_digits=self.env.company.currency_foreign_id.decimal_places,
                    )
                ),
                "refund_payments": "{0:.2f}".format(
                    float_round(
                        sum(refund_payments.mapped("foreign_amount")),
                        precision_digits=self.env.company.currency_foreign_id.decimal_places,
                    )
                ),
                "total": "{0:.2f}".format(
                    float_round(
                        sum(pos_payments.mapped("foreign_amount")),
                        precision_digits=self.env.company.currency_foreign_id.decimal_places,
                    )
                ),
            }
