from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

# Names of the bolivar currency (the current VES and the former VEF).
BOLIVAR_CURRENCY_NAMES = ("VES", "VEF")


class AccountMove(models.Model):
    _inherit = "account.move"

    is_donation = fields.Boolean(string="Is Donation", tracking=True)

    can_reverse_donation_move = fields.Boolean(compute="_compute_can_reverse_donation_move")

    is_stock_valuation_entry = fields.Boolean(compute="_compute_is_stock_valuation_entry")

    is_incoming_donation = fields.Boolean(
        string="Received Donation",
        compute="_compute_is_incoming_donation",
        help="The entry is a donation RECEIVED by the company. Not stored: a view "
        "cannot call `_is_incoming_donation()`, so it is exposed as a computed "
        "field to decide which document to offer.",
    )

    @api.depends("is_donation", "move_type", "company_id.donation_income_account_ids", "line_ids.account_id")
    def _compute_is_incoming_donation(self):
        for move in self:
            move.is_incoming_donation = move._is_incoming_donation()

    def _is_incoming_donation(self):
        """True if the entry is a donation RECEIVED by the company: a manual
        entry marked as donation with some line on one of the received
        donations accounts of the company. The direction is told by the
        account and not by the journal: one journal can hold both directions.
        Only manual entries (`entry`): a donation invoice (given) can use the
        same income account through the donation product."""
        self.ensure_one()
        income_accounts = self.company_id.donation_income_account_ids
        return bool(
            self.is_donation
            and self.move_type == "entry"
            and income_accounts
            and income_accounts & self.line_ids.account_id
        )

    @api.depends("stock_move_ids")
    def _compute_is_stock_valuation_entry(self):
        for move in self:
            move.is_stock_valuation_entry = bool(move.stock_move_ids)

    def _compute_can_reverse_donation_move(self):
        for move in self:
            move.can_reverse_donation_move = (
                self.env.user.has_group("l10n_ve_donation.group_donation_manager")
            )

    @api.constrains("is_donation", "line_ids", "line_ids.partner_id")
    def _check_partner_donation(self):
        """Validate journal items of a donation move use the company partner.
        The entries of a donation RECEIVED are not validated: their lines
        carry the donor (see `_is_incoming_donation`).

        Only the LINES are validated here -- the header (`move.partner_id`)
        is intentionally NOT constrained to the company partner: it
        represents the real counterparty (donor, when the company receives;
        beneficiary, when the company gives), so the donation certificate can
        show who it actually is instead of always "the company donates to
        the company".

        The line check itself only applies to move_type == 'entry' (manual
        journal entries, e.g. the stock picking accounting hook) -- that is
        the ONLY flow the donation certificate button is actually reachable
        from (invoices are out of scope: the invoice itself is already the
        certificate). For invoice-type moves (out_invoice/out_refund/...),
        Odoo's own core forces the receivable/payment-term line's partner to
        match the move's header partner for correct reconciliation -- that
        is not optional, so once the header is free to be the real
        beneficiary (see sale_order.py), invoice lines are expected and
        allowed to follow it, exactly like any regular sale."""
        for move in self:
            if not move.is_donation or move.move_type != "entry" or move._is_incoming_donation():
                continue
            company_partner = move.company_id.partner_id or self.env.company.partner_id
            for line in move.line_ids.filtered(lambda l: l.partner_id):
                if line.partner_id != company_partner:
                    raise ValidationError(
                        _(
                            "The contact on journal item '%(line)s' must be the company partner "
                            "('%(expected)s') when the entry is a donation. "
                            "Found: '%(found)s'.",
                            line=line.name or line.display_name,
                            expected=company_partner.name,
                            found=line.partner_id.name,
                        )
                    )

    def print_donation_receipt(self):
        """The receipt of the journal entry is the one of a money donation
        given. The valuation entry of a donation delivery has no receipt of
        its own: the receipt of its picking lists the products and their
        cost."""
        self.ensure_one()
        if self.is_stock_valuation_entry:
            pickings = self.stock_move_ids.picking_id
            raise UserError(_(
                "This entry is the stock valuation of a donation delivery and has no donation "
                "receipt. Print the Donation Receipt from the donation picking: %(pickings)s.",
                pickings=", ".join(pickings.mapped("name")) or "-",
            ))
        return self.env.ref("l10n_ve_donation.action_donation_receipt_account_move").report_action(self)

    def _get_donation_beneficiary(self):
        """Contact of the beneficiary of a donation entry: the contact of the
        header, unless it is the company itself (an entry without a
        beneficiary)."""
        self.ensure_one()
        partner = self.partner_id
        return partner if partner != self.company_id.partner_id else partner.browse()

    def _get_donation_concept_lines(self):
        """Descriptions of the concept of the receipt of a money donation:
        the debit lines that are not cash, bank or receivable/payable
        accounts (the expense of the donation), without repeating them."""
        self.ensure_one()
        liquidity_and_partner_types = ("asset_cash", "asset_receivable", "liability_payable")
        names = []
        for line in self.line_ids:
            if not line.debit or line.account_id.account_type in liquidity_and_partner_types:
                continue
            name = (line.name or "").strip()
            if name and name != self.ref and name not in names:
                names.append(name)
        return names

    def _get_donation_amounts(self):
        """Amounts of the donation for its documents: the total debit and
        the alternate amount of the entry, at the rates stored in it (the
        rates of its date), so that a reprint always gives the same
        numbers. See `_compute_donation_amounts`."""
        self.ensure_one()
        return self._compute_donation_amounts(
            self.company_id.currency_id,
            self.foreign_currency_id,
            sum(self.line_ids.mapped("debit")),
            self.foreign_debit,
            self.foreign_rate,
            self.foreign_inverse_rate,
        )

    @api.model
    def _compute_donation_amounts(
        self, company_currency, foreign_currency, company_amount, foreign_amount,
        foreign_rate, foreign_inverse_rate,
    ):
        """The amount of a donation document, the bolivar first, and its
        equivalent in the other currency with the rate (bolivars per unit of
        the other currency).

        `l10n_ve_rate` stores, for the alternate currency of the entry, the
        inverse of the company rate in `foreign_rate` and the company rate
        in `foreign_inverse_rate`. So the bolivars per unit of the other
        currency are `foreign_rate` when the company currency is the
        bolivar (alternate currency USD) and `foreign_inverse_rate` when the
        alternate currency is the bolivar (company currency USD, as in
        Higea). Returns `currency`, `amount`, `equivalent_currency`,
        `equivalent_amount` and `rate`; the equivalent is `False` when the
        entry has no alternate amount or rate."""
        result = {
            "currency": company_currency,
            "amount": company_amount,
            "equivalent_currency": False,
            "equivalent_amount": 0.0,
            "rate": 0.0,
        }
        if not (foreign_currency and foreign_currency != company_currency and foreign_amount):
            return result
        if (
            foreign_currency.name in BOLIVAR_CURRENCY_NAMES
            and company_currency.name not in BOLIVAR_CURRENCY_NAMES
        ):
            result.update(currency=foreign_currency, amount=foreign_amount)
            equivalent_currency, equivalent_amount, rate = company_currency, company_amount, foreign_inverse_rate
        else:
            equivalent_currency, equivalent_amount, rate = foreign_currency, foreign_amount, foreign_rate
        if rate:
            result.update(
                equivalent_currency=equivalent_currency,
                equivalent_amount=equivalent_amount,
                rate=rate,
            )
        return result

    def action_post(self):
        # Only the invoices that are posted by this call get a credit note:
        # calling it on an already posted one must not reverse it again.
        draft_invoices = self.filtered(
            lambda m: m.state == "draft" and m.is_donation and m.move_type == "out_invoice"
        )
        # Last chance to fill the partner of the lines, still in draft.
        self._fill_donation_entry_line_partner()
        res = super().action_post()

        # The l10n_ve_accountant alert wizard returns an action instead of
        # posting: the donation flow resumes when the wizard calls
        # `action_post` again.
        if isinstance(res, dict):
            return res

        donation_moves = draft_invoices.filtered(lambda m: m.state == "posted")
        for move in donation_moves:
            wizard = self.env["account.move.reversal"].with_context(
                active_ids=move.ids,
                active_model="account.move",
            ).create({
                "date": fields.Date.context_today(self),
                "journal_id": move.journal_id.id,
            })
            wizard.reverse_moves()
            credit_note = wizard.new_move_ids
            if credit_note.state == "draft":
                credit_note.action_post()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get("is_donation"):
            self._fill_donation_entry_line_partner()
        return res

    def _fill_donation_entry_line_partner(self):
        """The journal items of a donation entry carry the company partner
        (see `_check_partner_donation`). It is set while the entry is a
        draft, not when it is posted: a journal that locks the posted
        entries with a hash does not accept to write the partner of the
        lines of a posted entry. The lines that already have a partner are
        left as they are. The entries of a donation RECEIVED are not filled:
        their lines carry the donor."""
        for move in self.filtered(
            lambda m: m.is_donation and m.move_type == "entry" and m.state == "draft"
            and not m._is_incoming_donation()
        ):
            partner = move.company_id.partner_id or self.env.company.partner_id
            move.line_ids.filtered(lambda line: not line.partner_id).partner_id = partner

    def _l10n_ve_skip_refund_origin_validation(self):
        # La NC de donación nunca repite el producto de la factura original
        # (usa el producto de donación dedicado). La validación de
        # `l10n_ve_invoice` corre al publicar, y esta NC suele publicarse en
        # una llamada aparte (a mano, tras el wizard de alerta) donde ya no
        # existe la clave de contexto puesta en `_reverse_moves()` -- por
        # eso se excluye por el campo guardado `is_donation`.
        return self.is_donation or super()._l10n_ve_skip_refund_origin_validation()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Reverse a recordset of account.move.
        If cancel parameter is true, the reconcilable or liquidity lines
        of each original move will be reconciled with its reverse's.
        :param default_values_list: A list of default values to consider per move.
        ('type' & 'reversed_entry_id' are computed in the method).
        :return: An account.move recordset, reverse of the current self.
        """
        donation_moves = self.filtered(lambda move: move.is_donation and move.move_type != "entry")
        if donation_moves:
            reverse_moves = self.env['account.move']
            other_moves = self.env['account.move']
            other_default_values_list = []
            default_values_list = default_values_list or [{} for _move in self]
            for move, default_values in zip(self, default_values_list):
                if move not in donation_moves:
                    # A batch can mix donation invoices with other moves:
                    # the others are reversed by the standard flow below.
                    other_moves += move
                    other_default_values_list.append(default_values)
                    continue
                invoice_line_vals = move.product_line_donation()
                move_vals = {
                    "move_type": "out_refund",
                    "journal_id": move.journal_id.id,
                    "date": default_values.get("date", fields.Date.context_today(self)),
                    "invoice_date": move.invoice_date,
                    "ref": default_values.get("ref", move.ref),
                    "reversed_entry_id": move.id,
                    "partner_id": move.partner_id.id,
                    "is_donation": True,
                    "invoice_line_ids": invoice_line_vals,
                }
                # The exemption from the origin validation of
                # `l10n_ve_invoice` is decided by the stored `is_donation`
                # (see `_l10n_ve_skip_refund_origin_validation()`), not by a
                # context key: the credit note is posted in a later call.
                # Sin `skip_invoice_sync`: con esa llave el core no genera las
                # líneas de impuesto ni de cobro y la nota queda en cero (ver
                # `ea52357301`, que ya la quitó en 17.0).
                reverse_move = self.env['account.move'].with_context(
                    check_move_validity=False,
                ).create(move_vals)
                reverse_moves += reverse_move
            if other_moves:
                reverse_moves += super(AccountMove, other_moves)._reverse_moves(
                    other_default_values_list, cancel
                )
            return reverse_moves

        return super()._reverse_moves(default_values_list, cancel)

    def product_line_donation(self):
        """Adds the donation product lines to invoice_line_ids grouped by tax.
        The tax and payment term lines are generated by the core when the
        credit note is created in `_reverse_moves`.
        """
        product = self.env["product.template"].with_company(self.company_id).search(
            [("is_donation_product", "=", True)], limit=1
        )
        if not product:
            raise UserError(_("Please configure a donation product in the company settings. The product is type to service."))

        company = self.company_id or self.env.company
        donation_account_id = company.donation_account_id.id if company else False
        if not donation_account_id:
            raise UserError(_("Please configure a donation account in the company settings."))

        tax_data = self._get_tax_grouped_lines()

        invoice_line_vals = []
        for tax_key, data in tax_data.items():
            invoice_line_vals.append(
                Command.create(
                        {
                            "product_id": product.product_variant_ids[:1].id,
                            "account_id": donation_account_id,
                            "name": self.ref or product.name,
                            "quantity": 1,
                            "price_unit": data["base_amount"],
                            "tax_ids": [Command.set(data["taxes"].ids)],
                        }
                    )
                )
        return invoice_line_vals
 