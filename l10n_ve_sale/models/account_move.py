from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

from .l10n_ve_discount_document import (
    DiscountDocumentMixin,
    discount_apply,
    is_discount_applying,
)


class AccountMove(models.Model):
    _inherit = ["account.move", "l10n_ve.discount.document.mixin"]
    _name = "account.move"

    convert_currency_from_sale_order = fields.Boolean(
        related="company_id.convert_currency_from_sale_order",
    )
    use_invoice_rate_from_sale_order = fields.Boolean(
        related="company_id.use_invoice_rate_from_sale_order",
    )

    def _is_rate_date_locked(self):
        """Factura de cliente de una sola orden con "usar la tasa de la orden en la factura"
        activo: la Rate Date queda en la de la orden y no sigue a la fecha de la factura."""
        self.ensure_one()
        return (
            self.move_type == "out_invoice"
            and self.company_id.use_invoice_rate_from_sale_order
            and self.sale_order_count == 1
        ) or super()._is_rate_date_locked()

    def _discount_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(lambda line: line.display_type == "product")

    def _discount_line_gross(self, line):
        return line.price_unit * line.quantity

    discount_stage = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_approve", "Discount to Approve"),
            ("posted", "Posted"),
            ("cancel", "Cancelled"),
        ],
        string="Stage",
        compute="_compute_discount_stage",
        help="The state of the invoice with the discount approval as one more stage, "
        "like the sale order: a single status bar.",
    )

    @api.depends("state", "discount_approval_state")
    def _compute_discount_stage(self):
        for move in self:
            move.discount_stage = (
                "to_approve"
                if move.state == "draft" and move.discount_approval_state == "to_approve"
                else move.state
            )

    def _discount_is_editable(self):
        self.ensure_one()
        return self.state == "draft" and self.move_type == "out_invoice"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_discount_fields_protected(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_discount_fields_protected(vals)
        self._check_not_locked_by_approval(vals)
        return super().write(vals)

    def unlink(self):
        self._check_not_locked_by_approval({"unlink": True})
        return super().unlink()

    # ------------------------------------------------------------------
    # An invoice waiting for a discount approval is locked, like the order
    # ------------------------------------------------------------------
    APPROVAL_LOCK_BUTTONS = DiscountDocumentMixin.APPROVAL_LOCK_BUTTONS + ("action_post",)

    def _discount_is_waiting(self):
        return self.filtered(
            lambda move: move.discount_approval_state == "to_approve"
            and move.state == "draft"
        )

    def _check_not_locked_by_approval(self, vals):
        """While the invoice waits for its discount approval nothing can be
        edited (only cancelling it, or the approver approving / rejecting, which
        run with the internal marker)."""
        if self.env.su or is_discount_applying(self.env):
            return
        if not self._discount_is_waiting():
            return
        harmless = {key for key in vals if key.startswith(("message_", "activity_"))}
        changes = set(vals) - harmless - {"state"}
        if changes or vals.get("state", "cancel") != "cancel":
            raise UserError(self._discount_locked_message())

    @api.model
    def _discount_locked_message(self):
        return _(
            "This invoice is waiting for a discount approval and cannot be "
            "edited. A discount approver can approve or reject the "
            "discount, or the invoice can be cancelled."
        )

    def button_cancel(self):
        waiting = self.filtered(
            lambda move: move.discount_approval_state in ("exceeds", "to_approve")
        )
        waiting._discount_write_doc({"discount_approval_state": False})
        waiting._close_discount_approval_activities()
        return super().button_cancel()

    def button_draft(self):
        res = super().button_draft()
        self.filtered(
            lambda move: move.state == "draft" and move.move_type == "out_invoice"
        )._reset_discount_approval()
        return res

    def _discount_covered_by_origin(self, percent):
        """An invoice that comes from confirmed sale orders does not ask for the
        approval again when its discount is the one those orders were confirmed
        with (same scheme, not higher). If the discount was removed and applied
        again with something else, the approval is asked again."""
        self.ensure_one()
        orders = self.invoice_line_ids.sale_line_ids.order_id
        if not orders or self.discount_mode is False:
            return False
        precision = self.env["decimal.precision"].precision_get("Discount")
        for order in orders:
            if order.state not in ("sale", "done"):
                return False
            if order._discount_scheme() != self.discount_mode:
                return False
            order_percent, _limit = order._discount_effective_percent()
            if float_compare(percent, order_percent, precision_digits=precision) > 0:
                return False
        return True

    def action_post(self):
        # Same as the order: a discount over the maximum sends the invoice to
        # approval instead of posting it; approving the discount posts it.
        exceeding = self.filtered(lambda move: move.discount_approval_state == "exceeds")
        if exceeding:
            exceeding._send_to_approval()
            rest = self - exceeding
            if rest:
                super(AccountMove, rest).action_post()
            return exceeding._discount_approval_notification()
        return super().action_post()

    def _discount_owners(self):
        self.ensure_one()
        return self.invoice_user_id | self.create_uid

    def _discount_after_approval(self):
        # The natural next step: post the invoice. Its answer (the posting
        # alert of the localization, when it applies) goes back to the screen.
        return self.action_post()

    def _post(self, soft=True):
        self._check_discount_approved()
        return super()._post(soft)

    def _is_global_total_move(self):
        self.ensure_one()
        return self.discount_mode == "global_total" and self.move_type in (
            "out_invoice",
            "out_refund",
        )

    # Computed together with the totals (same method): the discount is taken
    # from the total the native computation just produced, so no second tax
    # summary is built and there is no re-entrant recompute of the amounts.
    global_total_discount = fields.Monetary(
        string="Global Discount Over Total",
        compute="_compute_amount",
        currency_field="currency_id",
        help="Global discount over the total, in the document currency.",
    )
    global_total_discount_company = fields.Monetary(
        string="Global Discount Over Total (Company Currency)",
        compute="_compute_amount",
        currency_field="company_currency_id",
    )

    def _get_global_total_discount_amounts(self):
        """(discount in the invoice currency, in the company currency) of a
        global discount over the total."""
        self.ensure_one()
        return self.global_total_discount, self.global_total_discount_company

    @api.depends(
        "discount_mode",
        "global_discount_type",
        "global_discount_percent",
        "global_discount_amount",
    )
    def _compute_amount(self):
        super()._compute_amount()
        for move in self:
            discount = discount_company = 0.0
            if move.is_invoice(True) and move._is_global_total_move():
                total = move.amount_total
                discount = move._get_global_total_discount(total, move.currency_id)
                if move.currency_id.is_zero(discount):
                    discount = 0.0
                else:
                    discount_company = move.company_currency_id.round(
                        abs(move.amount_total_signed) * discount / total
                    )
                    # The residual of a draft normally comes net of the discount
                    # (from tax_totals). When it equals the gross total it was
                    # taken from the lines (see l10n_ve_accountant): net it here.
                    if move.state == "draft" and move.currency_id.is_zero(
                        move.amount_residual - total
                    ):
                        move.amount_residual -= discount
                        move.amount_residual_signed -= discount_company
                    move.amount_total -= discount
                    move.amount_total_signed -= discount_company
                    move.amount_total_in_currency_signed -= discount
            move.global_total_discount = discount
            move.global_total_discount_company = discount_company

    @api.depends(
        "discount_mode",
        "global_discount_type",
        "global_discount_percent",
        "global_discount_amount",
        "global_total_discount",
        "global_total_discount_company",
    )
    def _compute_needed_terms(self):
        super()._compute_needed_terms()
        # With a payment term the receivable is split from base + taxes,
        # which do not know about the discount over the total.
        for move in self.filtered(
            lambda m: m.is_invoice(True) and m.invoice_payment_term_id and m._is_global_total_move()
        ):
            discount, discount_company = move._get_global_total_discount_amounts()
            terms = move.needed_terms
            total_currency = sum(v["amount_currency"] for v in terms.values())
            if move.currency_id.is_zero(discount) or move.currency_id.is_zero(total_currency):
                continue
            sign = 1 if total_currency > 0 else -1
            remaining, remaining_company = discount, discount_company
            keys = list(terms)
            for index, key in enumerate(keys):
                values = terms[key]
                if index == len(keys) - 1:
                    share, share_company = remaining, remaining_company
                else:
                    ratio = values["amount_currency"] / total_currency
                    share = move.currency_id.round(discount * ratio)
                    share_company = move.company_currency_id.round(discount_company * ratio)
                    remaining -= share
                    remaining_company -= share_company
                values["amount_currency"] -= sign * share
                values["balance"] -= sign * share_company

    def _get_move_discount_type(self):
        self.ensure_one()
        if self.discount_mode:
            return self._get_doc_discount_type()
        return super()._get_move_discount_type()

    @api.depends("company_id.discount_type", "discount_mode", "global_discount_type")
    def _compute_discount_type(self):
        super()._compute_discount_type()

    def _get_discount_allocation_account(self):
        self.ensure_one()
        if (
            self.discount_mode == "global_subtotal"
            and self.is_sale_document(include_receipts=True)
            and self.company_id.global_discount_account_id
        ):
            return self.company_id.global_discount_account_id
        return super()._get_discount_allocation_account()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        # Credit notes keep the scheme of the invoice they reverse.
        with discount_apply(self.env):
            return super()._reverse_moves(
                default_values_list=default_values_list, cancel=cancel
            )

    def _get_sale_conversion_pricelist_rule(self, line):
        """Regla de tarifa que pisaria la conversion de esta linea, si la hay.

        `account_invoice_pricelist` (OCA) recalcula price_unit desde la tarifa
        de la factura, asi que si esa tarifa define una regla para el producto
        habria dos logicas compitiendo por el mismo campo. Este helper la
        detecta para poder abortar en vez de dejar que una pise a la otra.

        El acceso es defensivo: `pricelist_id` en account.move lo agrega
        `account_invoice_pricelist`, que no es dependencia de este modulo. Si
        no esta instalado no hay reglas que respetar y la conversion procede.
        """
        self.ensure_one()
        if "pricelist_id" not in self._fields:
            return False
        pricelist = self.pricelist_id
        if not pricelist or not line.product_id:
            return False
        return pricelist._get_product_rule(
            line.product_id,
            quantity=line.quantity or 1.0,
            uom=line.product_uom_id,
            date=self.invoice_date or fields.Date.context_today(self),
        )

    @api.onchange("currency_id", "invoice_date")
    def _onchange_currency_sync_from_so(self):
        """Convierte los precios unitarios desde el Pedido de Ventas cuando
        cambia la moneda o la fecha de la factura.

        Espejo de lo que hace binaural_purchase con la Orden de Compra, con la
        diferencia de que en ventas el enlace es `sale_line_ids`, un Many2many:
        una linea de factura puede proceder de varias lineas de venta. Solo se
        convierten las lineas con un origen inequivoco (exactamente una linea
        de venta); las agrupadas se dejan como estan porque no hay un precio
        de origen unico del que partir.

        La conversion usa la fecha de la factura, que en esta localizacion es
        la fecha de la tasa (la fecha visible del documento es
        invoice_date_display).
        """
        if not self.invoice_origin or not self.currency_id:
            return

        # No se compara contra _origin para decidir si hay algo que hacer: al
        # volver a la moneda de partida dentro del mismo borrador (USD -> VES
        # -> USD) el valor coincidiria con el guardado y se saldria sin
        # recalcular, dejando el precio de la otra moneda. El onchange solo se
        # dispara cuando cambia currency_id o invoice_date, asi que recalcular
        # siempre es correcto: si la moneda vuelve a ser la de la orden, la
        # primera rama restituye su precio original.
        # Solo facturas de cliente. Las notas de credito y debito se emiten
        # siempre en base a su factura de origen, asi que recalcularlas desde
        # el pedido de ventas las desalinearia del documento que rectifican.
        if not (
            self.move_type == "out_invoice"
            and self.company_id.convert_currency_from_sale_order
        ):
            return

        invoice_date = self.invoice_date or fields.Date.context_today(self)
        precision = self.env["decimal.precision"].precision_get("Product Price")

        # Primero se validan todas las lineas: si alguna tiene regla de tarifa
        # no se convierte ninguna, para no dejar la factura a medio recalcular.
        blocking = []
        for line in self.invoice_line_ids:
            if len(line.sale_line_ids) != 1:
                continue
            if line.product_id.type not in ("consu", "service"):
                continue
            if self._get_sale_conversion_pricelist_rule(line):
                blocking.append(line.product_id.display_name)

        if blocking:
            # dict.fromkeys en vez de set(): con lineas duplicadas del mismo
            # producto (mismo precio y cantidad, cada una con su propia
            # sale_line_ids), el mismo nombre podia agregarse mas de una vez
            # y el mensaje de error repetia el producto. dict.fromkeys quita
            # los duplicados preservando el orden de aparicion.
            blocking = list(dict.fromkeys(blocking))
            raise UserError(
                _(
                    "The pricelist %(pricelist)s defines a rule for the "
                    "following products, so their price cannot be recalculated "
                    "from the sale order: %(products)s.\n\n"
                    "Both mechanisms set the same unit price and one would "
                    "override the other. Either remove the pricelist rule or "
                    "disable \"Convert Currency From Sale Order\".",
                    pricelist=self.pricelist_id.display_name,
                    products=", ".join(blocking),
                )
            )

        for line in self.invoice_line_ids:
            if len(line.sale_line_ids) != 1:
                continue

            so_line = line.sale_line_ids
            if line.product_id.type not in ("consu", "service"):
                continue

            order = so_line.order_id

            if self.currency_id == order.currency_id:
                # Misma moneda que la orden: no hay nada que convertir, la
                # fecha no interviene.
                new_price_unit = so_line.price_unit
            else:
                # Cualquier otra moneda -- incluida la alterna de la
                # compania -- convierte con invoice_date, la fecha de LA
                # FACTURA. No se usa so_line.foreign_price aqui a proposito:
                # ese campo esta calculado con la fecha de la ORDEN
                # (order.foreign_rate_date), que puede no coincidir con
                # invoice_date -- convert_currency_from_sale_order es un flag
                # independiente de use_invoice_rate_from_sale_order, asi que
                # la factura puede tener su propia fecha. El ticket pide
                # convertir "a la tasa de la Factura", no a la de la orden.
                new_price_unit = float_round(
                    order.currency_id._convert(
                        so_line.price_unit,
                        self.currency_id,
                        self.company_id,
                        invoice_date,
                        round=False,
                    ),
                    precision_digits=precision,
                )

            # Solo se toca price_unit: foreign_price es un campo calculado que
            # depende de el y de la fecha, asi que se recalcula solo.
            line.price_unit = new_price_unit
