from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, formatLang

SIDE_BY_TYPE = {"in_invoice": "vendor", "out_invoice": "customer"}
REFUND_TYPES = ("in_refund", "out_refund")


class AccountMove(models.Model):
    """Global deductible (percentage or fixed amount) for vendor bills and
    customer invoices, according to the company setting. The fields are
    `copy=False`: a duplicate does not carry it, credit and debit notes do.
    """

    _inherit = "account.move"

    DEDUCTIBLE_FIELDS = (
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
    )

    deductible_allowed = fields.Boolean(
        compute="_compute_deductible_allowed",
        help="The company enables the deductible for this type of document.",
    )
    is_deductible = fields.Boolean(
        string="Deductible",
        copy=False,
        tracking=True,
        help="Applies a global deductible (percentage or fixed amount) "
        "spread over every line of the document.",
    )
    global_deductible_type = fields.Selection(
        [("percent", "Percentage"), ("amount", "Fixed Amount")],
        string="Deductible Type",
        default="percent",
        copy=False,
        tracking=True,
    )
    global_deductible_percent = fields.Float(
        string="Deductible (%)", digits="Discount", copy=False, tracking=True
    )
    global_deductible_amount = fields.Monetary(
        string="Deductible Amount",
        currency_field="currency_id",
        copy=False,
        tracking=True,
    )
    global_deductible_reference_amount = fields.Monetary(
        string="Deducted Amount",
        currency_field="currency_id",
        compute="_compute_deductible_reference_amount",
        help="Reference: total amount removed from the document by the deductible.",
    )

    @api.depends("move_type", "company_id.use_deductible", "company_id.deductible_scope")
    def _compute_deductible_allowed(self):
        """True for invoices of the side (vendor / customer) the company enables
        for the deductible; credit notes only inherit it by reversal."""
        for move in self:
            company = move.company_id
            side = SIDE_BY_TYPE.get(move.move_type)
            move.deductible_allowed = bool(
                side and company.use_deductible and company.deductible_scope in (side, "both")
            )

    @api.model
    def _get_base_line_sync_extra_fields(self):
        return super()._get_base_line_sync_extra_fields() + [
            "global_deductible_discount_percent"
        ]

    def write(self, vals):
        """Block deductible changes on non-draft documents; turning it off
        resets the percentage and the amount."""
        if any(field in vals for field in self.DEDUCTIBLE_FIELDS):
            posted = self.filtered(lambda move: move.state != "draft")
            if posted:
                raise UserError(
                    _(
                        "The deductible can only be changed on draft documents. "
                        "Reset %s to draft first.",
                        ", ".join(posted.mapped("display_name")),
                    )
                )
        if "is_deductible" in vals and not vals["is_deductible"]:
            vals = dict(vals, global_deductible_percent=0.0, global_deductible_amount=0.0)
        if any(field in vals for field in self.DEDUCTIBLE_FIELDS):
            # a new value of the document: the amounts of the lines are proposed again
            self.invoice_line_ids.filtered("global_deductible_manual").write(
                {"global_deductible_manual": False}
            )
        activating = self.filtered(lambda move: not move.is_deductible) if vals.get("is_deductible") else self.browse()
        result = super().write(vals)
        activating.filtered("is_deductible")._check_deductible_enabled()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """A new deductible document needs the type enabled by the company."""
        moves = super().create(vals_list)
        moves.filtered("is_deductible")._check_deductible_enabled()
        return moves

    def _get_deductible_copy_values(self):
        """Values that make a document created from this one (credit note,
        debit note with copied lines, replacement of a reversed document) keep
        the same deductible."""
        self.ensure_one()
        if not self.is_deductible or self.move_type not in SIDE_BY_TYPE:
            return {}
        return {field: self[field] for field in self.DEDUCTIBLE_FIELDS}

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """A credit note of a deductible document keeps its deductible, so it
        credits exactly what the document amounted to."""
        if not default_values_list:
            default_values_list = [{} for _move in self]
        for move, default_values in zip(self, default_values_list):
            default_values.update(move._get_deductible_copy_values())
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    def _get_deductible_issues(self):
        """Reasons why this document cannot be deductible (list of messages)."""
        self.ensure_one()
        issues = []
        for line in self._get_deductible_product_lines():
            name = line.product_id.display_name or line.name or ""
            if line.discount or line.discount_fixed:
                issues.append(_("%s: lines cannot have a previous discount.", name))
        return issues

    def _get_deductible_warning(self, title):
        """Onchange warning listing why the document cannot be deductible."""
        issues = self._get_deductible_issues()
        return {"warning": {"title": title, "message": "\n".join(issues)}} if issues else {}

    @api.onchange("is_deductible")
    def _onchange_is_deductible(self):
        for move in self:
            if not move.is_deductible:
                move.global_deductible_percent = move.global_deductible_amount = 0.0
                continue
            warning = move._get_deductible_warning(_("Deductible cannot be enabled"))
            if warning:
                move.is_deductible = False
                return warning

    @api.onchange("global_deductible_type")
    def _onchange_deductible_type(self):
        for move in self:
            move.global_deductible_percent = move.global_deductible_amount = 0.0

    @api.onchange("invoice_line_ids")
    def _onchange_invoice_line_ids_deductible(self):
        for move in self.filtered("is_deductible"):
            warning = move._get_deductible_warning(_("Invalid lines for a deductible document"))
            if warning:
                return warning

    @api.onchange(*DEDUCTIBLE_FIELDS)
    def _onchange_deductible_values(self):
        """The document's deductible changed: propose again the amount and the
        percent of every line, assigned explicitly as a change of the native
        `discount` does, so each line refreshes its own subtotal in the form."""
        for move in self:
            for line in move._get_deductible_product_lines():
                line.global_deductible_manual = False
            move._propose_deductible_line_values()

    @api.onchange("invoice_line_ids")
    def _onchange_deductible_line_values(self):
        """A line changed (price, quantity, or the amount typed by the user):
        keep what the user typed, spread the rest again and refresh the
        percent each line shows."""
        for move in self:
            move._propose_deductible_line_values()

    def _propose_deductible_line_values(self):
        self.ensure_one()
        amounts = self._get_deductible_line_amounts()
        for line in self._get_deductible_product_lines():
            line.global_deductible_line_amount = amounts.get(line, 0.0)
        self._refresh_deductible_line_percents()

    def _refresh_deductible_line_percents(self):
        self.ensure_one()
        percents = self._get_deductible_line_percents()
        for line in self._get_deductible_product_lines():
            line.global_deductible_discount_percent = percents.get(line, 0.0)

    @api.constrains(*DEDUCTIBLE_FIELDS, "move_type", "reversed_entry_id", "invoice_line_ids")
    def _check_deductible(self, check_sum=True):
        """Enabled document type (or credit note of a deductible one), no
        previous discount, value limits and per-line amounts adding
        up to the amount entered."""
        for move in self.filtered("is_deductible"):
            move._check_deductible_document()
            if issues := move._get_deductible_issues():
                raise ValidationError(_("The deductible cannot be applied:\n%s", "\n".join(issues)))
            if move.global_deductible_type == "percent":
                move._check_deductible_percent()
            else:
                move._check_deductible_amount(check_sum=check_sum)

    def _post(self, soft=True):
        """The amounts typed in the lines must add up before posting."""
        self.filtered("is_deductible")._check_deductible()
        return super()._post(soft=soft)

    def _check_deductible_document(self):
        """The document type accepts the deductible: an invoice, or a credit
        note of a deductible document."""
        if self.move_type in REFUND_TYPES and self.reversed_entry_id.is_deductible:
            return
        if self.move_type not in SIDE_BY_TYPE:
            raise ValidationError(
                _("The deductible can only be used on vendor bills and customer invoices.")
            )

    def _check_deductible_enabled(self):
        """The company enables the deductible for the type of document. Only
        checked when it is activated, so a document that already was deductible
        stays usable if the setting changes; notes inherit it from their origin."""
        if self.env.context.get("deductible_inherit"):
            return
        for move in self:
            origin = move.reversed_entry_id | move.debit_origin_id
            if not (move.deductible_allowed or any(origin.mapped("is_deductible"))):
                raise ValidationError(
                    _(
                        "The deductible is not enabled for this company and type "
                        "of document. Enable it in the accounting settings."
                    )
                )

    def _check_deductible_percent(self):
        """The percentage is above 0 and below 100."""
        if not 0.0 < self.global_deductible_percent < 100.0:
            raise ValidationError(
                _(
                    "The deductible percentage must be greater than 0 and "
                    "less than 100: 100% of a document cannot be deducted."
                )
            )

    def _check_deductible_amount(self, check_sum=True):
        """The amount is above 0 and below the original total, and the amounts
        taken off the lines add up to it (`check_sum`; the lines of a document
        are written one by one, so the sum is only checked on the document)."""
        currency, amount = self.currency_id, self.global_deductible_amount
        gross = self._get_deductible_gross_total()
        digits = currency.decimal_places
        if (
            float_compare(amount, 0.0, precision_digits=digits) <= 0
            or float_compare(amount, gross, precision_digits=digits) >= 0
        ):
            raise ValidationError(
                _(
                    "The deductible amount must be greater than 0 and "
                    "less than the original document total (%s): 100%% of a "
                    "document cannot be deducted.",
                    formatLang(self.env, gross, currency_obj=currency),
                )
            )
        distributed = sum(self._get_deductible_product_lines().mapped("global_deductible_line_amount"))
        if check_sum and float_compare(distributed, amount, precision_rounding=currency.rounding):
            raise ValidationError(
                _(
                    "The amounts deducted on the lines (%(lines)s) must add "
                    "up to the deductible amount (%(total)s).",
                    lines=formatLang(self.env, distributed, currency_obj=currency),
                    total=formatLang(self.env, amount, currency_obj=currency),
                )
            )
