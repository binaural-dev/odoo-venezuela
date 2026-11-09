from odoo import _, api, fields, models

RECEIVABLE_PAYABLE = ("asset_receivable", "liability_payable")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_ve_open_amount = fields.Monetary(
        string="Open amount", currency_field="currency_id", compute="_compute_l10n_ve_open_amount",
        help="Pending amount of the line, always positive, in the currency of the line.")

    @api.depends("amount_residual_currency")
    def _compute_l10n_ve_open_amount(self):
        for line in self:
            line.l10n_ve_open_amount = abs(line.amount_residual_currency)

    def _l10n_ve_reconcile_kind(self):
        """Clase de la línea para el asistente: `invoice`, `payment`, `advance`, `cross`
        (asiento de cruce de anticipo), `note` (nota que se concilia desde su documento) u `other`."""
        self.ensure_one()
        move = self.move_id
        if move.is_advance_move:
            return "cross"
        if move._l10n_ve_reconcile_is_special_note():
            return "note"
        if self.account_id.is_advance_account:
            payment = move.origin_payment_id
            return "advance" if payment and payment.is_advance_payment else "other"
        if self.account_id.account_type not in RECEIVABLE_PAYABLE:
            return "other"
        if move.is_invoice(include_receipts=True):
            return "invoice"
        return "payment" if move.origin_payment_id else "other"

    def _l10n_ve_reconcile_extra_blockers(self):
        """Gancho: motivos adicionales de bloqueo (lista de textos) que aportan otros módulos,
        como la sucursal. Se llama sobre la selección completa."""
        return []

    def _l10n_ve_reconcile_classify(self):
        """Clasifica la selección. Devuelve un dict con:
        `handled` (False: la conciliación nativa sigue su curso), `ok` (se puede conciliar con el
        asistente), `case` (`payment` o `advance`, según el origen), `origins` (línea del pago o anticipo),
        `invoices` (líneas de factura) y `reasons` (motivos de bloqueo). Se admite un único origen contra una
        o varias facturas."""
        kinds = {line.id: line._l10n_ve_reconcile_kind() for line in self}
        involved = set(kinds.values())
        invoices = self.filtered(lambda line: kinds[line.id] == "invoice")
        origins = self.filtered(lambda line: kinds[line.id] in ("payment", "advance"))
        advance_involved = bool(involved & {"advance", "cross"})
        result = {
            "handled": bool(advance_involved or "note" in involved or (invoices and origins)),
            "ok": False,
            "case": False,
            "origins": origins,
            "invoices": invoices,
            "reasons": [],
        }
        if not result["handled"]:
            return result

        reasons = result["reasons"]
        if "cross" in involved:
            reasons.append(_(
                "One of the lines belongs to an advance cross entry. Crosses are reconciled and "
                "undone from the invoice, since doing it here would break the link with the origin payment."))
        if "note" in involved:
            reasons.append(_(
                "One of the lines belongs to a debit/credit note of IGTF or of the exchange difference. "
                "Such notes are reconciled from their own document to keep the date and rate of the payment."))
        if "advance" in involved and not invoices:
            reasons.append(_("An advance can only be applied against an invoice."))
        if advance_involved and "other" in involved:
            reasons.append(_(
                "An advance can only be applied against receivable or payable accounts of an invoice, "
                "not against another account."))
        if len(origins) > 1:
            reasons.append(_(
                "Select a single payment or advance to apply against one or several invoices. To pay an "
                "invoice with several payments, reconcile each payment on its own: each payment converts only "
                "what is left of it and each advance creates its own cross entries, so with more than one "
                "origin the result would depend on the order."))
        if len(self.partner_id.commercial_partner_id) > 1:
            reasons.append(_("The lines belong to different partners."))
        if len(self.company_id) > 1:
            reasons.append(_("The lines belong to different companies."))
        if any(line.parent_state != "posted" or line.reconciled for line in self):
            reasons.append(_("All lines must be posted and not reconciled."))
        if any((invoice.balance > 0) == (origin.balance > 0) for invoice in invoices for origin in origins):
            reasons.append(_(
                "The payments and the invoices do not go in opposite directions "
                "(for example a payment received against a vendor bill)."))
        reasons.extend(self._l10n_ve_reconcile_extra_blockers())

        if not reasons:
            result["ok"] = True
            result["case"] = kinds[origins.id]
        return result

    def action_l10n_ve_reconcile_assistant(self):
        """Abre el asistente para estas líneas. Se crea en el servidor y se abre ya guardado: las filas
        de facturas son registros reales y sus botones de orden pueden ejecutarse."""
        context = {"active_model": "account.move.line", "active_ids": self.ids}
        wizard = self.env["l10n_ve.reconcile.assistant"].with_context(**context).create({})
        return dict(wizard._reopen(), context=dict(context, dialog_size="extra-large"))
