from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    foreign_cash_register_balance_end_real = fields.Monetary(
        string="Foreign Ending Balance", readonly=True
    )
    foreign_cash_register_balance_start = fields.Monetary(
        string="Foreign Starting Balance", readonly=True
    )
    foreign_cash_register_total_entry_encoding = fields.Monetary(
        compute="_compute_foreign_cash_balance",
        string="Foreign Total Cash Transaction",
        readonly=True,
    )
    foreign_cash_register_balance_end = fields.Monetary(
        compute="_compute_foreign_cash_balance",
        string="Foreign Theoretical Closing Balance",
        help="Opening balance summed to all cash transactions.",
        readonly=True,
    )
    foreign_cash_register_difference = fields.Monetary(
        compute="_compute_foreign_cash_balance",
        string="Foreign Before Closing Difference",
        help="Difference between the theoretical closing balance and the real closing balance.",
        readonly=True,
    )
    foreign_cash_real_transaction = fields.Monetary(string="Foreign Transaction", readonly=True)
    foreign_cash_journal_id = fields.Many2one(
        "account.journal", compute="_compute_cash_all", store=True
    )

    def _loader_params_pos_session(self):
        res = super()._loader_params_pos_session()
        res["search_params"]["fields"].append("foreign_cash_register_balance_start")
        return res

    def _loader_params_pos_bill(self):
        res = super()._loader_params_pos_bill()
        res["search_params"]["fields"].append("currency_id")
        return res

    def action_pos_session_open(self):
        res = super().action_pos_session_open()
        # we only open sessions that haven't already been opened
        for session in self.filtered(lambda session: session.state == "opening_control"):
            values = {}
            if session.config_id.cash_control and not session.rescue:
                foreign_cash_journal = self.payment_method_ids.filtered(
                    lambda x: x.is_cash_count and x.is_foreign_currency
                )[:1].journal_id
                if not foreign_cash_journal:
                    raise ValidationError(
                        _("You can't open the session without foreign cash payment method")
                    )

                last_session = self.search(
                    [("config_id", "=", session.config_id.id), ("id", "!=", session.id)], limit=1
                )

                session.foreign_cash_register_balance_start = (
                    last_session.foreign_cash_register_balance_end_real
                )
            session.write(values)
        return res

    @api.depends("foreign_cash_journal_id")
    def _compute_cash_all(self):
        res = super()._compute_cash_all()
        for session in self:
            session.foreign_cash_journal_id = False
            cash_journal = session.payment_method_ids.filtered(
                lambda x: x.is_cash_count and x.is_foreign_currency
            )[:1].journal_id

            if not cash_journal:
                continue
            session.foreign_cash_journal_id = cash_journal
        return res

    @api.depends("payment_method_ids", "order_ids", "cash_register_balance_start")
    def _compute_cash_balance(self):
        for session in self:
            cash_payment_method = session.payment_method_ids.filtered("is_cash_count")[:1]
            if cash_payment_method:
                total_cash_payment = 0.0
                last_session = session.search(
                    [("config_id", "=", session.config_id.id), ("id", "<", session.id)], limit=1
                )
                result = self.env["pos.payment"]._read_group(
                    [
                        ("session_id", "=", session.id),
                        ("payment_method_id", "=", cash_payment_method.id),
                    ],
                    ["amount"],
                    ["session_id"],
                )
                if result:
                    total_cash_payment = result[0]["amount"]

                if session.state == "closed":
                    session.cash_register_total_entry_encoding = (
                        session.cash_real_transaction + total_cash_payment
                    )
                else:
                    session.cash_register_total_entry_encoding = (
                        sum(
                            session.statement_line_ids.filtered(
                                lambda stat: stat.journal_id.id == self.cash_journal_id.id
                            ).mapped("amount")
                        )
                        + total_cash_payment
                    )

                session.cash_register_balance_end = (
                    last_session.cash_register_balance_end_real
                    + session.cash_register_total_entry_encoding
                )
                session.cash_register_difference = (
                    session.cash_register_balance_end_real - session.cash_register_balance_end
                )
            else:
                session.cash_register_total_entry_encoding = 0.0
                session.cash_register_balance_end = 0.0
                session.cash_register_difference = 0.0

    @api.depends("payment_method_ids", "order_ids", "foreign_cash_register_balance_start")
    def _compute_foreign_cash_balance(self):
        for session in self:
            cash_payment_method = session.payment_method_ids.filtered(
                lambda x: x.is_cash_count and x.is_foreign_currency
            )[:1]
            if cash_payment_method:
                total_cash_payment = 0.0
                last_session = session.search(
                    [("config_id", "=", session.config_id.id), ("id", "<", session.id)], limit=1
                )
                result = self.env["pos.payment"]._read_group(
                    [
                        ("session_id", "=", session.id),
                        ("payment_method_id", "=", cash_payment_method.id),
                    ],
                    ["foreign_amount"],
                    ["session_id"],
                )
                if result:
                    total_cash_payment = result[0]["foreign_amount"]

                if session.state == "closed":
                    session.foreign_cash_register_total_entry_encoding = (
                        session.foreign_cash_real_transaction + total_cash_payment
                    )
                else:
                    session.foreign_cash_register_total_entry_encoding = (
                        sum(session.statement_line_ids.mapped("amount")) + total_cash_payment
                    )

                session.foreign_cash_register_balance_end = (
                    last_session.foreign_cash_register_balance_end_real
                    + session.foreign_cash_register_total_entry_encoding
                )
                session.foreign_cash_register_difference = (
                    session.foreign_cash_register_balance_end_real
                    - session.foreign_cash_register_balance_end
                )
            else:
                session.foreign_cash_register_total_entry_encoding = 0.0
                session.foreign_cash_register_balance_end = 0.0
                session.foreign_cash_register_difference = 0.0

    def get_closing_control_data(self):
        res = super().get_closing_control_data()
        self.ensure_one()
        orders = self.order_ids.filtered(lambda o: o.state == "paid" or o.state == "invoiced")
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")

        # Default Cash Payment Methods

        cash_payment_method_ids = self.payment_method_ids.filtered(lambda pm: pm.type == "cash")
        default_cash_payment_method_id = (
            cash_payment_method_ids[0] if cash_payment_method_ids else None
        )
        foreign_default_cash_payment_method_id = self.payment_method_ids.filtered(
            lambda pm: pm.is_foreign_currency and pm.type == "cash"
        )
        # --------------------

        foreign_total_default_cash_payment_amount = (
            sum(
                payments.filtered(
                    lambda p: p.payment_method_id == default_cash_payment_method_id
                ).mapped("foreign_amount")
            )
            if default_cash_payment_method_id
            else 0
        )

        # --------------------

        total_foreign_default_cash_payment_amount = (
            sum(
                payments.filtered(
                    lambda p: p.payment_method_id == foreign_default_cash_payment_method_id
                ).mapped("amount")
            )
            if foreign_default_cash_payment_method_id
            else 0
        )
        foreign_total_foreign_default_cash_payment_amount = (
            sum(
                payments.filtered(
                    lambda p: p.payment_method_id == foreign_default_cash_payment_method_id
                ).mapped("foreign_amount")
            )
            if foreign_default_cash_payment_method_id
            else 0
        )

        other_payment_method_ids = (
            self.payment_method_ids - cash_payment_method_ids
            if cash_payment_method_ids
            else self.payment_method_ids
        )
        cash_in_count = 0
        cash_out_count = 0
        cash_in_out_list = []
        foreign_cash_in_out_list = []
        last_session = self.search(
            [("config_id", "=", self.config_id.id), ("id", "!=", self.id)], limit=1
        )

        # -----------------------
        # Base Currency

        for cash_move in (
            self.sudo()
            .statement_line_ids.filtered(lambda stat: stat.journal_id.id == self.cash_journal_id.id)
            .sorted("create_date")
        ):
            if cash_move.amount > 0:
                cash_in_count += 1
                name = f"Cash in {cash_in_count}"
            else:
                cash_out_count += 1
                name = f"Cash out {cash_out_count}"
            cash_in_out_list.append(
                {
                    "name": cash_move.payment_ref if cash_move.payment_ref else name,
                    "amount": cash_move.amount,
                }
            )

        # -------------------------
        # Foreign Currency

        for cash_move in (
            self.sudo()
            .statement_line_ids.filtered(
                lambda stat: stat.journal_id.id == self.foreign_cash_journal_id.id
            )
            .sorted("create_date")
        ):
            if cash_move.foreign_amount > 0:
                cash_in_count += 1
                name = f"Cash in {cash_in_count}"
            else:
                cash_out_count += 1
                name = f"Cash out {cash_out_count}"

            foreign_cash_in_out_list.append(
                {
                    "name": cash_move.payment_ref if cash_move.payment_ref else name,
                    "amount": cash_move.foreign_amount,
                }
            )

        # ------------------------

        res["other_payment_methods"] = [
            {
                "name": pm.name,
                "amount": sum(
                    orders.payment_ids.filtered(lambda p: p.payment_method_id == pm).mapped(
                        "amount"
                    )
                ),
                "foreign_amount": sum(
                    orders.payment_ids.filtered(lambda p: p.payment_method_id == pm).mapped(
                        "foreign_amount"
                    )
                ),
                "number": len(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)),
                "is_foreign_currency": pm.is_foreign_currency,
                "id": pm.id,
                "type": pm.type,
            }
            for pm in other_payment_method_ids
        ]

        res["foreign_default_cash_details"] = (
            {
                "name": foreign_default_cash_payment_method_id.name,
                "amount": last_session.cash_register_balance_end_real
                + total_foreign_default_cash_payment_amount
                + sum(
                    self.sudo()
                    .statement_line_ids.filtered(
                        lambda stat: stat.journal_id.id == self.foreign_cash_journal_id.id
                    )
                    .mapped("amount")
                ),
                "foreign_amount": last_session.foreign_cash_register_balance_end_real
                + foreign_total_foreign_default_cash_payment_amount
                + sum(
                    self.sudo()
                    .statement_line_ids.filtered(
                        lambda stat: stat.journal_id.id == self.foreign_cash_journal_id.id
                    )
                    .mapped("foreign_amount")
                ),
                "opening": last_session.cash_register_balance_end_real,
                "foreign_opening": last_session.foreign_cash_register_balance_end_real,
                "payment_amount": total_foreign_default_cash_payment_amount,
                "payment_foreign_amount": foreign_total_foreign_default_cash_payment_amount,
                "moves": foreign_cash_in_out_list,
                "id": foreign_default_cash_payment_method_id.id,
            }
            if foreign_default_cash_payment_method_id
            else None
        )

        if not self.config_id.cash_control:
            return res

        res["default_cash_details"]["amount"] -= sum(
            self.sudo()
            .statement_line_ids.filtered(
                lambda stat: stat.journal_id.id == self.foreign_cash_journal_id.id
            )
            .mapped("amount")
        )
        res["default_cash_details"]["foreign_amount"] = 0
        res["default_cash_details"]["payment_foreign_amount"] = 0
        res["default_cash_details"]["foreign_opening"] = 0
        res["default_cash_details"]["moves"] = cash_in_out_list

        return res

    def _validate_session(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        res = super()._validate_session(
            balancing_account=balancing_account,
            amount_to_balance=amount_to_balance,
            bank_payment_method_diffs=bank_payment_method_diffs,
        )
        if self.order_ids or self.sudo().statement_line_ids:
            self.foreign_cash_real_transaction = sum(
                self.sudo()
                .statement_line_ids.filtered(
                    lambda stat: stat.journal_id.id == self.foreign_cash_journal_id.id
                )
                .mapped("foreign_amount")
            )
        self._post_foreign_statement_difference(self.foreign_cash_register_difference, False)
        return res

    def _post_statement_difference(self, amount, is_opening):
        res = super()._post_statement_difference(amount, is_opening)
        return res

    def _post_foreign_statement_difference(self, amount, is_opening):
        if amount:
            rate = self.env["res.currency"]._get_conversion_rate(
                self.foreign_currency_id,
                self.currency_id,
                self.env.company,
                fields.Date.context_today(self),
            )
            if self.config_id.cash_control:
                st_line_vals = {
                    "journal_id": self.foreign_cash_journal_id.id,
                    "amount": amount * rate,
                    "foreign_amount": amount,
                    "date": self.statement_line_ids.sorted()[-1:].date
                    or fields.Date.context_today(self),
                    "pos_session_id": self.id,
                }

            if amount < 0.0:
                if not self.foreign_cash_journal_id.loss_account_id:
                    raise UserError(
                        _(
                            "Please go on the %s journal and define a Loss Account. This account will be used to record cash difference.",
                            self.foreign_cash_journal_id.name,
                        )
                    )

                st_line_vals["payment_ref"] = _(
                    "Cash difference observed during the counting (Loss)"
                ) + (_(" - opening") if is_opening else _(" - closing"))
                if not is_opening:
                    st_line_vals[
                        "counterpart_account_id"
                    ] = self.foreign_cash_journal_id.loss_account_id.id
            else:
                # self.cash_register_difference  > 0.0
                if not self.foreign_cash_journal_id.profit_account_id:
                    raise UserError(
                        _(
                            "Please go on the %s journal and define a Profit Account. This account will be used to record cash difference.",
                            self.foreign_cash_journal_id.name,
                        )
                    )

                st_line_vals["payment_ref"] = _(
                    "Cash difference observed during the counting (Profit)"
                ) + (_(" - opening") if is_opening else _(" - closing"))
                if not is_opening:
                    st_line_vals[
                        "counterpart_account_id"
                    ] = self.foreign_cash_journal_id.profit_account_id.id

            self.env["account.bank.statement.line"].create(st_line_vals)

    def post_closing_foreign_cash_details(self, counted_cash):
        """
        Calling this method will try store the cash details during the session closing.

        :param counted_cash: float, the total cash the user counted from its cash register
        If successful, it returns {'successful': True}
        Otherwise, it returns {'successful': False, 'message': str, 'redirect': bool}.
        'redirect' is a boolean used to know whether we redirect the user to the back end or not.
        When necessary, error (i.e. UserError, AccessError) is raised which should redirect the user to the back end.
        """
        self.ensure_one()
        check_closing_session = self._cannot_close_session()
        if check_closing_session:
            return check_closing_session

        if not self.foreign_cash_journal_id:
            # The user is blocked anyway, this user error is mostly for developers that try to call this function
            raise UserError(_("There is no foreign cash register in this session."))

        self.foreign_cash_register_balance_end_real = counted_cash
        return {"successful": True}

    def set_foreign_cashbox_pos(self, cashbox_value, notes):
        difference = cashbox_value - self.foreign_cash_register_balance_start
        self.foreign_cash_register_balance_start = cashbox_value
        self.sudo()._post_foreign_statement_difference(difference, True)
        self._post_foreign_cash_details_message("Opening", difference, notes)

    def _post_foreign_cash_details_message(self, state, difference, notes):
        message = ""
        if difference:
            message = (
                f"{state} difference: "
                f"{self.foreign_currency_id.symbol + ' ' if self.foreign_currency_id.position == 'before' else ''}"
                f"{self.foreign_currency_id.round(difference)} "
                f"{self.foreign_currency_id.symbol if self.foreign_currency_id.position == 'after' else ''}<br/>"
            )
        if notes:
            message += notes.replace("\n", "<br/>")
        if message:
            self.message_post(body=message)

    def try_cash_in_out(self, _type, amount, reason, extras):
        sign = 1 if _type == "in" else -1
        sessions = self.filtered("cash_journal_id")
        if not sessions:
            raise UserError(_("There is no cash payment method for this PoS Session"))

        is_base = extras.get("currency") == self.env.company.currency_id.id

        def get_rate(is_base):
            if is_base:
                return 1

            currency_id = (
                self.env.company.currency_id if is_base else self.env.company.currency_foreign_id
            )
            foreign_currency_id = (
                self.env.company.currency_foreign_id if is_base else self.env.company.currency_id
            )

            return self.env["res.currency"]._get_conversion_rate(
                currency_id, foreign_currency_id, self.env.company, fields.Date.context_today(self)
            )

        def get_foreign_rate(is_base):
            if not is_base:
                return 1

            currency_id = (
                self.env.company.currency_id if is_base else self.env.company.currency_foreign_id
            )
            foreign_currency_id = (
                self.env.company.currency_foreign_id if is_base else self.env.company.currency_id
            )

            return self.env["res.currency"]._get_conversion_rate(
                currency_id, foreign_currency_id, self.env.company, fields.Date.context_today(self)
            )

        new_amount = amount * get_rate(is_base)
        foreign_amount = amount * get_foreign_rate(is_base)

        self.env["account.bank.statement.line"].create(
            [
                {
                    "pos_session_id": session.id,
                    "journal_id": session.cash_journal_id.id
                    if is_base
                    else session.foreign_cash_journal_id.id,
                    "amount": sign * new_amount,
                    "foreign_amount": sign * foreign_amount,
                    "date": fields.Date.context_today(self),
                    "payment_ref": "-".join([session.name, extras["translatedType"], reason]),
                }
                for session in sessions
            ]
        )

        message_content = [
            f"Cash {extras['translatedType']}",
            f'- Amount: {extras["formattedAmount"]}',
        ]
        if reason:
            message_content.append(f"- Reason: {reason}")
        self.message_post(body="<br/>\n".join(message_content))
