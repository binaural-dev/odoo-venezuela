from odoo import api, fields, models, Command, _
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError

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
            retention_line_id = payment.retention_line_ids[0]
            move = payment.move_id
            move_name = (
                account_move_name_by_retention_type[payment.retention_id.type_retention]
                + f"-{payment.retention_id.number}"
                + f"-{retention_line_id.move_id.name}"
            )
            if payment.retention_id.type_retention == "islr":
                move_name += f"-{retention_line_id.payment_concept_id.name[:5]}"
            if payment.retention_id.type_retention == "municipal":
                move_name += (
                    f"-{retention_line_id.economic_activity_id.name}"
                    f"-{retention_line_id.economic_activity_id.branch_id.name}"
                )

            vals_to_change = {"name": move_name, "is_manually_modified": True}
            move.write(vals_to_change)
        return res

    def _generate_move_vals(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        """
        A retention payment's move must land in the same fiscal period as (and use
        the same exchange rate as) the invoice it retains from, even though
        payment.date stays as the retention's own date_accounting chosen by the
        user. Writing move.date after the move is created/posted is NOT enough
        (and was tried and reverted): the move's amounts are already computed
        using payment.date's rate at generation time, so forcing only the date
        label afterwards desyncs date from the rate actually used, producing a
        bogus exchange difference on reconciliation. Instead, inject
        l10n_ve_conversion_date (read by l10n_ve_accountant's
        _prepare_move_lines_per_type override) BEFORE generating the move, so the
        liquidity line is converted with the invoice's rate, then align 'date' to
        that same value so the two never drift apart.
        """
        self.ensure_one()
        if self.is_retention and self.retention_line_ids:
            invoice_date = self.retention_line_ids[0].move_id.date
            if invoice_date:
                vals = super(
                    AccountPayment, self.with_context(l10n_ve_conversion_date=invoice_date)
                )._generate_move_vals(write_off_line_vals, force_balance, line_ids)
                vals['date'] = invoice_date
                return vals
        return super()._generate_move_vals(write_off_line_vals, force_balance, line_ids)

    def unlink(self):
        for payment in self:
            if any(isinstance(id, api.NewId) for id in self.retention_line_ids.ids):
                payment.retention_line_ids = False
            else:
                payment.retention_line_ids = False
        return super().unlink()

    def compute_retention_amount_from_retention_lines(self):
        """
        Compute the amount from the retention lines.
        """
        for payment in self:
            payment.amount = sum(
                payment.retention_line_ids.mapped("retention_amount"))

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

    def action_draft(self):

        if self.env.context.get('bypass_retention_lock'):
            return super().action_draft()
        
        for payment in self:
            
            if payment.is_retention and payment.state != 'cancel':
                raise UserError(_(
                    "You cannot reset this payment to draft because it is a retention linked to voucher %s. "
                    "You must void or cancel the retention document first."
                ) % payment.retention_id.display_name)
        return super().action_draft()

    def action_cancel(self):

        if self.env.context.get('bypass_retention_lock'):
            return super().action_cancel()
        
        for payment in self:
            
            if payment.is_retention and payment.state != 'cancel':
                raise UserError(_(
                    "You cannot cancel this payment because it is a retention linked to voucher %s. "
                    "You must void or cancel the retention document first."
                ) % payment.retention_id.display_name)
        return super().action_cancel()