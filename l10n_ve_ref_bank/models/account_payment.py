from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_post(self):
        res = super().action_post()
        if self.env.company.ref_required and self.journal_id.ref_length_required > 0:
            self.validate_bank_payment_reference_length()
            for payment in self:
                found_pay = self.env["account.payment"].search(
                    [
                        ("id", "!=", payment.id),
                        ("ref", "=", payment.ref),
                        ("company_id.id", "=", payment.company_id.id),
                        ("move_id.state", "=", "posted"),
                        ("journal_id.type", "=", "bank"),
                    ]
                )
                if found_pay:
                    raise ValidationError(
                        _("A payment already exists with the same reference (memo)")
                    )

        return res

    def validate_bank_payment_reference_length(self):
        for payment in self:
            if (
                payment.journal_id.ref_length_required > 0
                and payment.journal_id.type == "bank"
            ):
                if len(str(payment.ref)) != payment.journal_id.ref_length_required:
                    raise ValidationError(
                        _(
                            f"No cumple con la condición de longitud bancaria de { payment.journal_id.ref_length_required} caracteres en el campo memo"
                        )
                    )
