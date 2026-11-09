from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

WIDGET_FIELDS = (
    "invoice_outstanding_credits_debits_widget",
    "invoice_outstanding_credits_debits_widget_advance_payment",
)


class L10nVeReconcileAssistant(models.TransientModel):
    _name = "l10n_ve.reconcile.assistant"
    _description = "Reconciliation assistant"

    line_ids = fields.Many2many("account.move.line", string="Selected items", readonly=True)
    case = fields.Selection(
        [("payment", "Payment to invoices"), ("advance", "Advance to invoices"), ("blocked", "Blocked")],
        readonly=True,
    )
    scenario_label = fields.Char(readonly=True)
    blocked_reason = fields.Text(readonly=True)
    origin_line_ids = fields.Many2many(
        "account.move.line", "l10n_ve_reconcile_assistant_origin_rel", "wizard_id", "line_id",
        string="Payments and advances", readonly=True)
    invoice_line_ids = fields.Many2many(
        "account.move.line", "l10n_ve_reconcile_assistant_invoice_rel", "wizard_id", "line_id",
        string="Invoices to pay", readonly=True)
    item_ids = fields.One2many("l10n_ve.reconcile.assistant.item", "wizard_id", string="Application")
    pending_warning = fields.Boolean(readonly=True)
    origin_summary = fields.Text(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lines = self.env["account.move.line"].browse(self.env.context.get("active_ids", []))
        info = lines._l10n_ve_reconcile_classify()
        res["line_ids"] = [Command.set(lines.ids)]
        reasons = list(info["reasons"])
        rows = []
        if info["ok"]:
            pairs = self._default_pairs(info["origins"], info["invoices"].move_id)
            rows = self._compute_preview(pairs)
            missing = [row for row in rows if row["missing"]]
            if missing:
                reasons.append(_(
                    "There is no amount available to apply %(origin)s to: %(invoice)s",
                    origin=", ".join(self.env["account.move.line"].browse(
                        [row["origin_line_id"] for row in missing]).move_id.mapped("name")),
                    invoice=", ".join(self.env["account.move"].browse(
                        [row["invoice_id"] for row in missing]).mapped("name"))))
        elif not info["handled"]:
            reasons.append(_("The selection is not a payment or advance against invoices."))
        if reasons:
            res.update(case="blocked", blocked_reason="\n".join(reasons))
            return res
        res.update(
            case=info["case"],
            scenario_label=self._scenario_label(info["origins"], info["invoices"]),
            origin_line_ids=[Command.set(info["origins"].ids)],
            invoice_line_ids=[Command.set(info["invoices"].ids)],
            item_ids=[
                Command.create(dict(
                    self._item_values(row), origin_line_id=row["origin_line_id"],
                    invoice_id=row["invoice_id"], sequence=10 * index))
                for index, row in enumerate(rows, 1)
            ],
            pending_warning=self._has_pending(rows),
            origin_summary=self._origin_summary(rows),
        )
        return res

    @api.model
    def _has_pending(self, rows):
        """True si alguna factura sigue con monto por pagar tras aplicar los pares de la vista previa."""
        moves = self.env["account.move"]
        return any(
            not moves.browse(row["invoice_id"]).currency_id.is_zero(row["pending_after"])
            for row in rows
        )

    @api.model
    def _default_pairs(self, origins, invoices):
        """Pares (origen, factura) en el orden inicial: las facturas más antiguas primero. El usuario lo
        cambia arrastrando las filas."""
        return [(origins, invoice) for invoice in invoices.sorted(
            lambda move: (move.invoice_date or move.date, move.id))]

    @api.model
    def _scenario_label(self, origins, invoices):
        """Frase que dice qué se cruza contra qué, p. ej. "1 pago contra 3 facturas"."""
        origin_label = _("1 payment") if origins._l10n_ve_reconcile_kind() == "payment" else _("1 advance")
        invoice_label = _("1 invoice") if len(invoices) == 1 else _("%s invoices", len(invoices))
        return _("%(origins)s against %(invoices)s", origins=origin_label, invoices=invoice_label)

    @api.model
    def _item_values(self, row):
        """Valores de una fila de la vista previa que se guardan en la línea del asistente."""
        return {key: value for key, value in row.items()
                if key not in ("origin_line_id", "invoice_id", "missing")}

    @api.model
    def _widget_entry(self, invoice, origin):
        """Fila del widget de la factura para la línea origen (monto completo del origen)."""
        field = WIDGET_FIELDS[1] if origin.account_id.is_advance_account else WIDGET_FIELDS[0]
        invoice.invalidate_recordset([field])
        widget = invoice[field] or {}
        return next((entry for entry in widget.get("content", []) if entry["id"] == origin.id), None)

    @api.model
    def _compute_preview(self, pairs):
        """Vista previa de la aplicación de cada par (origen, factura), en el orden dado y sin escribir
        nada: lo que ofrece el origen con lo que le queda tras los pares anteriores (convertido a la fecha
        y tasa del widget de su factura), limitado a lo que queda por pagar de la factura.

        Para un anticipo imita el cruce de `_create_advance_payment_move`, que no convierte con la tasa
        exacta sino que consume `saldo x base / monto del widget` con los montos ya redondeados, y resta
        el IGTF del cruce si el diario lo aplica. Así el saldo que queda del anticipo puede diferir en
        centavos de un reparto ideal, y la vista previa muestra lo que de verdad va a pasar."""
        remaining = {}
        pending = {}
        rows = []
        for origin, invoice in pairs:
            payment = origin.move_id.origin_payment_id
            company = invoice.company_id
            full = abs(origin.amount_residual_currency)
            balance = remaining.get(origin.id, full)
            entry = self._widget_entry(invoice, origin)
            date = entry["date_to_convert"] if entry else False
            pending_before = pending.get(invoice.id, abs(invoice.amount_residual))
            widget_amount = (
                origin.currency_id._convert(balance, invoice.currency_id, company, date) if entry else 0.0)
            has_offer = not invoice.currency_id.is_zero(widget_amount)
            apply = min(widget_amount, pending_before)
            has_apply = not invoice.currency_id.is_zero(apply)
            igtf = 0.0
            if origin.account_id.is_advance_account:
                base = apply
                applied_origin = origin.currency_id.round(balance * base / widget_amount) if has_offer else 0.0
                if payment.journal_id.is_igtf and has_apply:
                    igtf_origin = abs(payment.calculate_igtf_for_payment(
                        invoice, applied_origin, payment.currency_id, date))
                    igtf = payment.currency_id._convert(igtf_origin, invoice.currency_id, company, date)
                    if invoice.currency_id.compare_amounts(base + igtf, widget_amount) <= 0:
                        base = invoice.currency_id.round(base + igtf)
                        applied_origin = origin.currency_id.round(balance * base / widget_amount)
                    else:
                        apply -= igtf
                balance_after = max(balance - applied_origin, 0.0)
            elif has_offer:
                # Pago: lo concilia el motor nativo con la tasa del widget. Si la factura absorbe todo lo
                # que ofrece el origen, queda agotado; si no, se convierte lo aplicado con esa misma tasa
                to_origin = invoice.currency_id._get_conversion_rate(
                    invoice.currency_id, origin.currency_id, company, date)
                absorbed = invoice.currency_id.compare_amounts(apply, widget_amount) >= 0
                balance_after = 0.0 if absorbed else max(balance - apply * to_origin, 0.0)
            else:
                balance_after = balance
            remaining[origin.id] = balance_after
            pending[invoice.id] = pending_before - apply
            rate = origin.currency_id._get_conversion_rate(
                origin.currency_id, invoice.currency_id, company, date or fields.Date.today())
            conditions = []
            if payment.keep_alter_value_vef:
                conditions.append(_("Keeps the value in foreign currency"))
            if payment.journal_id.is_igtf:
                conditions.append(_("IGTF journal"))
            rows.append({
                "origin_line_id": origin.id,
                "invoice_id": invoice.id,
                "missing": not entry,
                "conversion_date": date,
                # Siempre en moneda de la compañía por unidad de la otra (p. ej. 41 Bs por USD), no al revés
                "rate": 1 / rate if origin.currency_id == origin.company_currency_id else rate,
                "widget_amount": widget_amount,
                "apply_amount": apply,
                "igtf_amount": igtf,
                "pending_after": invoice.currency_id.round(pending_before - apply),
                "origin_before": origin.currency_id.round(balance),
                "origin_applied": origin.currency_id.round(balance - balance_after),
                "origin_remaining": origin.currency_id.round(balance_after),
                "origin_conditions": " · ".join(conditions),
            })
        return rows

    @api.model
    def _origin_summary(self, rows):
        """Una línea por origen con lo que se cruza de él en total (con el IGTF de los cruces) y lo que
        queda: así se ve de un vistazo cuánto sale de un pago o anticipo, sin sumar columnas."""
        per_origin = {}
        for row in rows:
            data = per_origin.setdefault(row["origin_line_id"], {"crossed": 0.0})
            data["crossed"] += row["origin_applied"]
            data["left"] = row["origin_remaining"]
        lines = []
        for origin_id, data in per_origin.items():
            origin = self.env["account.move.line"].browse(origin_id)
            currency = origin.currency_id
            lines.append(_(
                "%(origin)s: %(crossed)s are crossed out of %(total)s; %(left)s remain",
                origin=origin.move_id.name, crossed=currency.format(data["crossed"]),
                total=currency.format(abs(origin.amount_residual_currency)), left=currency.format(data["left"])))
        return "\n".join(lines)

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reconcile documents"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.onchange("item_ids")
    def _onchange_item_ids(self):
        """Al arrastrar una fila (campo `sequence`) se recalcula la vista previa con el nuevo orden: cada
        par toma lo que queda de su origen y de su factura tras los anteriores."""
        items = self.item_ids.sorted("sequence")
        rows = self._compute_preview([(item.origin_line_id, item.invoice_id) for item in items])
        for item, row in zip(items, rows):
            item.update(self._item_values(row))
        self.pending_warning = self._has_pending(rows)
        self.origin_summary = self._origin_summary(rows)

    def action_confirm(self):
        """Aplica cada origen a su factura, par por par y en el orden elegido. Cada aplicación lee el
        widget de nuevo (el residual del origen y de la factura ya bajó con la anterior) y todo corre en la
        transacción del botón: si una falla, ninguna queda hecha."""
        self.ensure_one()
        if self.case == "blocked":
            raise UserError(self.blocked_reason)
        info = self.line_ids._l10n_ve_reconcile_classify()
        if not info["ok"]:
            raise UserError(_("The selection changed since the assistant was opened. Open it again.")
                            + "\n" + "\n".join(info["reasons"]))
        for item in self.item_ids.sorted("sequence"):
            origin, invoice = item.origin_line_id, item.invoice_id
            invoice.invalidate_recordset(["amount_residual", *WIDGET_FIELDS])
            if origin.reconciled or invoice.currency_id.is_zero(invoice.amount_residual):
                continue
            invoice = invoice.with_company(invoice.company_id).with_context(
                **invoice._l10n_ve_reconcile_apply_context())
            invoice.js_assign_outstanding_line(origin.id)
        return {"type": "ir.actions.act_window_close"}
