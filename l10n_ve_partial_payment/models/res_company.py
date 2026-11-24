"""Per-company toggle for the partial-application widget.

Only the flag relevant to this module's actual scope (the "Add" popover on
the payment widget) is defined here. The other flags from the general
scope's config table (Registrar Pago, Conciliar Pagos, Asientos Contables,
multi-invoice distribution, credit notes) belong to later tasks that build
those flows -- adding them now would be dead configuration with no behavior
behind it.

"Show/edit remaining balance" is *not* one of those still-dead entries: a
live preview of the payment's remaining balance, plus a pre-filled
(editable) suggested amount, are already part of this same "Add" popover's
behavior (added after functional review), gated by this same flag and by
``group_partial_payment_apply`` -- with no config flag of their own. See
``static/src/js/account_payment_field_partial.js``.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    partial_pay_from_outstanding = fields.Boolean(
        string="Enable partial application from outstanding payments on invoice",
        default=False,
    )
