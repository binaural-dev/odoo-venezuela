from odoo import models, fields, api, _
from odoo.tools import float_compare


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    split_transactions = fields.Boolean(
        string="Identify Customer",
        default=False,
        help="The customer must be identified in the PoS to pay with this "
        "method, and the cross move of its foreign-currency payments is "
        "created per payment instead of one per currency and session.",
    )

    currency_setting_ids = fields.One2many(
        "pos.payment.method.currency",
        "payment_method_id",
        string="Currency Settings",
        help="Cross journals of the foreign currencies this method accepts.",
    )

    def write(self, vals):
        res = super().write(vals)
        if "currency_ids" in vals:
            for method in self:
                method.currency_setting_ids.filtered(
                    lambda setting: setting.currency_id not in method.currency_ids
                ).unlink()
        return res

    def _get_currency_settings(self, currency):
        """Settings of this method for ``currency``: cross journals, and what
        the modules that extend ``pos.payment.method.currency`` add (IGTF).
        Empty when the method has none for that currency."""
        self.ensure_one()
        return self.currency_setting_ids.filtered(
            lambda setting: setting.currency_id == currency
        )[:1]

    @api.model
    def _load_pos_data_fields(self, config):
        res = super()._load_pos_data_fields(config)
        for name in ("split_transactions", "currency_setting_ids"):
            if name not in res:
                res.append(name)
        return res

    def _create_bank_payment_line(
        self, session, amount, account=None, message=None, partner=None,
        foreign_currency=None, amount_currency=None,
    ):
        """Settle a bank payment in the currency of the register, with the
        alternate amount stamped by ``_create_payment_line``, as Odoo 19 did.

        Core creates the ``account.payment`` in the currency the customer paid
        with and lets it convert to the company currency at the rate of the
        day: $12.04 at 917.246984 is 11,043.65, not the 11,043.20 the order
        was sold for, and the difference came out as an exchange difference
        entry at the reconciliation (Odoo 19 posted exactly the amount of the
        order). The currency the customer paid with stays on
        ``pos.payment.foreign_currency_id`` and ``amount_currency``.
        """
        return super()._create_bank_payment_line(
            session, amount, account, message, partner, None, None
        )

    def _create_payment_line(
        self, session, amount, account=None, message=None, partner=None,
        foreign_currency=None, amount_currency=None,
    ):
        """Stamp the rate and the alternate amount the register charged on the
        entry that settles a POS payment, before core reconciles it.

        Core creates that entry (a cash statement line or an ``account.payment``)
        from the grouped amount of the payments and reconciles it with the
        ``payment_term`` line of the closing entry or of the invoice right
        after. ``l10n_ve_accountant`` would value its lines at the rate of the
        day, so the alternate amounts are written while the lines are still
        open: written after the reconciliation they would leave an exchange
        difference entry behind.

        ``pos.session._create_session_account_move`` and
        ``pos.order._generate_pos_order_invoice`` leave in the context the
        payments they group (``l10n_ve_pos_payments_data``); any other caller
        (cash in/out, differences) is left untouched.
        """
        lines = super()._create_payment_line(
            session, amount, account, message, partner, foreign_currency, amount_currency
        )
        data = self.env.context.get("l10n_ve_pos_payments_data")
        if not data or not lines or self.type == "pay_later":
            return lines
        rounding = session.currency_id.rounding
        entry = next(
            (
                entry
                for entry in data["entries"]
                if entry["metadata"]["payment_method_id"] == self
                and (entry["metadata"]["foreign_currency_id"].id or False)
                == (foreign_currency or False)
                and float_compare(entry["metadata"]["amount"], amount, precision_rounding=rounding) == 0
            ),
            None,
        )
        if not entry:
            return lines
        payments = entry["metadata"]["payments"]
        foreign_amount = abs(entry["metadata"]["foreign_amount"])
        for payment_move in lines.move_id:
            self._set_payment_move_rate(payment_move, payments, data["session_closing"])
            for line in payment_move.line_ids:
                line.write(
                    {
                        "not_foreign_recalculate": True,
                        "foreign_debit": foreign_amount if line.debit > 0 else 0.0,
                        "foreign_credit": foreign_amount if line.credit > 0 else 0.0,
                    }
                )
        return lines

    def _set_payment_move_rate(self, payment_move, payments, session_closing):
        """Rate of a payment entry: the one of the config when the session
        closes (a single entry per method), the one of its own payment when it
        settles an invoice."""
        config = payments.pos_order_id.config_id[:1]
        if session_closing:
            rate_vals = {
                "foreign_rate": config.foreign_rate,
                "foreign_inverse_rate": config.foreign_inverse_rate,
            }
            if payment_move.origin_payment_id:
                payment_move.origin_payment_id.write(rate_vals)
            return
        payment = payments.filtered(lambda p: not p.is_change)[:1] or payments[:1]
        rate_vals = config._get_move_foreign_rate_vals(payment.foreign_rate)
        if not rate_vals:
            return
        payment_move.write(rate_vals)
        if payment_move.origin_payment_id:
            payment_move.origin_payment_id.write(
                {
                    "foreign_rate": rate_vals["foreign_rate"],
                    "foreign_inverse_rate": rate_vals["foreign_inverse_rate"],
                }
            )
