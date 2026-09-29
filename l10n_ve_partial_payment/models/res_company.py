"""Per-company toggle for the partial-application widget.

Only the flag relevant to this module's actual scope (the "Add" popover on
the payment widget) is defined here. The other flags from the general
scope's config table (Registrar Pago, Conciliar Pagos, Asientos Contables,
multi-invoice distribution, credit notes, show/edit remaining balance)
belong to later tasks that build those flows -- adding them now would be
dead configuration with no behavior behind it.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    partial_pay_from_outstanding = fields.Boolean(
        string="Enable partial application from outstanding payments on invoice",
        default=False,
    )
