from odoo import api, fields, models, Command
from odoo.tools.float_utils import float_round


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_retention = fields.Boolean(
        string="Is retention",
        help="Check this box if this payment is a retention",
        default=False,
        copy=False,
    )

    payment_type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        copy=False,
    )
    retention_id = fields.Many2one("account.retention", ondelete="cascade")

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "payment_id",
        string="Retention Lines",
        store=True,
        copy=False,
    )

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        domain="[('tax_ids', '!=', False)]",
        string="Invoice Lines",
        store=True,
        copy=False,
    )

    retention_ref = fields.Char(
        string="Retention reference",
        related="retention_id.number",
        store=True,
        copy=False,
    )

    retention_foreign_amount = fields.Float(
        compute="_compute_retention_foreign_amount", store=True, copy=False
    )

    @api.depends("date")
    def _compute_rate(self):
        for payment in self:
            if payment.is_retention and payment.foreign_rate:
                continue
            return super()._compute_rate()

    def _synchronize_to_moves(self, changed_fields):
        """
        Override the original method to change the name of the move based on the retention type
        using the retention's number and the invoice's name of the retention.
        """
        res = super()._synchronize_to_moves(changed_fields)
        account_move_name_by_retention_type = {
            "iva": "RIV",
            "islr": "RIS",
            "municipal": "RM",
        }
        for payment in self.filtered("is_retention").with_context(
            skip_account_move_synchronization=True
        ):
            if not all((payment.retention_line_ids, payment.retention_id.number)):
                continue
            move = payment.move_id
            move_name = (
                account_move_name_by_retention_type[payment.retention_id.type_retention]
                + f"-{payment.retention_id.number}"
                + f"-{payment.retention_line_ids[0].move_id.name}"
            )
            if payment.retention_id.type_retention == "islr":
                move_name += f"-{payment.retention_line_ids[0].payment_concept_id.name[:5]}"

            vals_to_change = {"name": move_name}
            move.write(vals_to_change)
            move.line_ids.write(vals_to_change)
        return res

    def unlink(self):
        for payment in self:
            if any(isinstance(id, models.NewId) for id in self.retention_line_ids.ids):
                payment.retention_line_ids = False
            else:
                payment.retention_line_ids = Command.clear()
        return super().unlink()

    def compute_retention_amount_from_retention_lines(self):
        """
        Compute the amount from the retention lines.
        """
        for payment in self:
            payment.amount = sum(payment.retention_line_ids.mapped("retention_amount"))

    @api.depends("retention_line_ids")
    def _compute_retention_foreign_amount(self):
        for payment in self:
            payment.retention_foreign_amount = abs(
                sum(
                    payment.retention_line_ids.mapped(
                        lambda l: float_round(
                            l.foreign_retention_amount,
                            precision_digits=l.retention_id.foreign_currency_id.decimal_places,
                        )
                    )
                )
            )
