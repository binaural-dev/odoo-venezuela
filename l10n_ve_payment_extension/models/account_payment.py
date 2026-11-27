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

    retention_resync_pending = fields.Boolean(
        string="Retention Resync Pending",
        compute="_compute_retention_resync_pending",
        help=(
            "True when this is a retention payment and its retention no"
            " longer matches its invoice's current data (see"
            " account.retention.retention_resync_pending)."
        ),
    )

    @api.depends("is_retention", "retention_id.retention_resync_pending")
    def _compute_retention_resync_pending(self):
        for payment in self:
            payment.retention_resync_pending = bool(
                payment.is_retention and payment.retention_id.retention_resync_pending
            )

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

    def _get_retention_foreign_rate_date(self):
        """Fecha de tasa con la que se valora en moneda alterna el asiento de
        una retencion: la fecha de la factura retenida.

        Es la MISMA regla que usa cada linea del asiento
        (`account.move.line._get_foreign_rate_date`), que delega aqui para
        que el importe alterno del pago y el del asiento no puedan divergir.
        Devuelve False si no aplica (no es retencion, o sus lineas no
        pertenecen a una unica factura con fecha); en ese caso quien llama
        usa el criterio por defecto.
        """
        self.ensure_one()
        if not self.is_retention:
            return False
        invoice = self.retention_line_ids.mapped("move_id")
        if len(invoice) != 1:
            return False
        return invoice.invoice_date or invoice.date or False

    @api.depends("amount", "currency_id", "date", "is_retention", "retention_line_ids.move_id")
    def _compute_foreign_amount(self):
        """El importe alterno de una retencion se convierte con la fecha de
        tasa de su asiento (la de la factura retenida), no con `date` (la
        fecha contable de la retencion): con tasas distintas entre ambas
        fechas el campo quedaba distinto al monto alterno del asiento."""
        super()._compute_foreign_amount()
        for payment in self.filtered("is_retention"):
            rate_date = payment._get_retention_foreign_rate_date()
            if rate_date and payment.currency_id != payment.foreign_currency_id:
                payment.foreign_amount = payment.currency_id._convert(
                    payment.amount,
                    payment.foreign_currency_id,
                    payment.company_id,
                    rate_date,
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

            vals_to_change = {"name": move_name, "is_manually_modified": True, "foreign_rate": retention_line_id.move_id.foreign_rate, "foreign_inverse_rate": retention_line_id.move_id.foreign_inverse_rate}
            move.write(vals_to_change)
        return res


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