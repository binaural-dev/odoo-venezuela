from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.l10n_ve_discount_document import DISCOUNT_MODES, GLOBAL_MODES

SCHEMES = [
    ("lines", "On all the lines of the document"),
    ("global_subtotal", "Global discount over the subtotal"),
    ("global_total", "Global discount over the total"),
]
TYPES = [("percent", "Percentage"), ("amount", "Fixed Amount")]


class L10nVeDiscountWizard(models.TransientModel):
    _name = "l10n_ve.discount.wizard"
    _description = "Document discount wizard"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    scheme = fields.Selection(
        SCHEMES,
        string="Apply",
        required=True,
        default=lambda self: self._default_scheme(),
    )
    # One "Type" field per scheme: each can offer its own allowed types (a
    # selection list cannot depend on another field of the record). The window
    # shows the one of the chosen scheme.
    type_lines = fields.Selection(
        TYPES, string="Type", default=lambda self: self._default_type("lines")
    )
    type_global_subtotal = fields.Selection(
        TYPES, string="Type", default=lambda self: self._default_type("global_subtotal")
    )
    type_global_total = fields.Selection(
        TYPES, string="Type", default=lambda self: self._default_type("global_total")
    )
    discount_type = fields.Selection(
        TYPES,
        compute="_compute_discount_type",
        inverse="_inverse_discount_type",
    )
    value = fields.Float(string="Discount", digits="Product Price", required=True)
    current_mode = fields.Selection(DISCOUNT_MODES, compute="_compute_current_mode")

    @api.depends("scheme", "type_lines", "type_global_subtotal", "type_global_total")
    def _compute_discount_type(self):
        for wizard in self:
            wizard.discount_type = wizard["type_%s" % (wizard.scheme or "lines")] or "percent"

    def _inverse_discount_type(self):
        for wizard in self:
            wizard["type_%s" % (wizard.scheme or "lines")] = wizard.discount_type

    @api.model
    def _allowed_types(self, scheme):
        """Types the company lets anybody apply with `scheme`: both when the
        discount method is not limited, only the ticked ones when it is."""
        company = self.env.company
        if not company.discount_method_limit_enabled:
            return [key for key, _label in TYPES]
        if scheme == "lines":
            flags = {
                "percent": company.discount_allow_line_percent,
                "amount": company.discount_allow_line_amount,
            }
        else:
            allowed = (
                company.discount_allow_global_subtotal
                if scheme == "global_subtotal"
                else company.discount_allow_global_total
            )
            flags = {"percent": allowed, "amount": allowed}
        return [key for key, _label in TYPES if flags[key]]

    @api.model
    def _allowed_schemes(self):
        return [key for key, _label in SCHEMES if self._allowed_types(key)]

    @api.model
    def _default_scheme(self):
        allowed = self._allowed_schemes()
        return allowed[0] if allowed else "lines"

    @api.model
    def _default_type(self, scheme):
        allowed = self._allowed_types(scheme)
        return allowed[0] if allowed else "percent"

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """The window only offers what the company allows; the check of
        `_check_discount_method_allowed` stays as the server side guard."""
        res = super().fields_get(allfields, attributes)
        if "selection" in res.get("scheme", {}):
            allowed = set(self._allowed_schemes())
            res["scheme"]["selection"] = [
                item for item in res["scheme"]["selection"] if item[0] in allowed
            ]
        for scheme, _label in SCHEMES:
            info = res.get("type_%s" % scheme)
            if info and "selection" in info:
                allowed = set(self._allowed_types(scheme))
                info["selection"] = [item for item in info["selection"] if item[0] in allowed]
        return res

    def _get_document(self):
        self.ensure_one()
        if self.res_model not in ("sale.order", "account.move"):
            raise UserError(_("Discounts cannot be applied to this kind of document."))
        document = self.env[self.res_model].browse(self.res_id).exists()
        if not document:
            raise UserError(_("The document no longer exists."))
        if document._name == "account.move" and document.move_type != "out_invoice":
            raise UserError(_("Discounts can only be applied to customer invoices."))
        document.check_access("write")
        return document

    @api.depends("res_model", "res_id")
    def _compute_current_mode(self):
        for wizard in self:
            document = (
                self.env[wizard.res_model].browse(wizard.res_id)
                if wizard.res_model in ("sale.order", "account.move")
                else False
            )
            wizard.current_mode = document.discount_mode if document else False

    def action_apply(self):
        self.ensure_one()
        document = self._get_document()
        if (
            self.scheme in ("global_subtotal", "global_total")
            and not document.company_id.global_discount_account_id
        ):
            raise UserError(
                _(
                    "Set the Global Discount Account in the Binaural settings "
                    "before applying a global discount."
                )
            )
        document._apply_discount(self.scheme, self.discount_type, self.value)
        return {"type": "ir.actions.act_window_close"}

    def action_remove(self):
        self.ensure_one()
        self._get_document()._remove_discount()
        return {"type": "ir.actions.act_window_close"}
