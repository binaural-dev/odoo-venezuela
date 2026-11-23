from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        string="Foreign Currency",
        help="Foreign currency for the company",
    )
    l10n_ve_require_daily_rate = fields.Boolean(
        string="Require Rate of the Day",
        default=True,
        help="If checked, documents need a rate dated exactly on their date and an error "
        "is raised when there is none. If unchecked, the most recent previous rate is "
        "used instead (for example, Friday's rate on a weekend).",
    )

    def write(self, vals):
        before_currency = self.foreign_currency_id
        res = super().write(vals)
        if "foreign_currency_id" in vals and before_currency:
            lines = self.env["account.move.line"].search(
                [("foreign_currency_id", "=", before_currency.id)]
            )
            if lines:
                raise ValidationError(
                    _(
                        "The currency already has accounting movements, you cannot deactivate this foreign currency"
                    )
                )
        return res

    @api.constrains("foreign_currency_id", "currency_id")
    def _check_foreign_currency_id(self):
        for rec in self:
            if "currency_id" in rec._fields and rec.currency_id == rec.foreign_currency_id:
                raise UserError(
                    _("The currency foreign must be different from the currency of the company")
                )
