from contextlib import contextmanager

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.l10n_ve_invoice.tools.discount import spread_amount

DISCOUNT_MODES = [
    ("line_percent", "Lines (Percentage)"),
    ("line_amount", "Lines (Fixed Amount)"),
    ("global_subtotal", "Global on Subtotal"),
    ("global_total", "Global on Total"),
]
GLOBAL_MODES = ("global_subtotal", "global_total")
# Marca interna del servidor (vive en el cursor, no en el contexto): un cliente
# RPC puede enviar cualquier clave de contexto, asi que no sirve para saltarse
# las validaciones del descuento.
DISCOUNT_APPLY_KEY = "l10n_ve_discount_apply"
PROTECTED_DISCOUNT_FIELDS = (
    "discount_mode",
    "global_discount_type",
    "global_discount_percent",
    "global_discount_amount",
    "discount_approval_state",
)


@contextmanager
def discount_apply(env):
    """The code inside applies the discount of the document itself (wizard,
    invoicing, reversal, copy): the line guards and the protection of the
    scheme fields stand aside. Not reachable from a client."""
    cache = env.cr.cache
    cache[DISCOUNT_APPLY_KEY] = cache.get(DISCOUNT_APPLY_KEY, 0) + 1
    try:
        yield
    finally:
        cache[DISCOUNT_APPLY_KEY] = max(cache.get(DISCOUNT_APPLY_KEY, 1) - 1, 0)


def is_discount_applying(env):
    return env.cr.cache.get(DISCOUNT_APPLY_KEY, 0) > 0
APPROVER_GROUP = "l10n_ve_sale.group_discount_approver"
DISCOUNT_APPROVAL_ACTIVITY = "l10n_ve_sale.mail_activity_type_discount_approval"


class DiscountDocumentMixin(models.AbstractModel):
    """Discount state shared by sale orders and customer invoices.

    A document carries ONE discount scheme at a time (`discount_mode`): a
    percentage or fixed amount on every line, or a global discount over the
    subtotal / the total. The scheme lives on the document, never on the
    lines, so the wizard and the line guards can tell which one applies.
    """

    _name = "l10n_ve.discount.document.mixin"
    _description = "Document discount scheme"

    discount_mode = fields.Selection(
        DISCOUNT_MODES,
        string="Discount Scheme",
        copy=True,
        readonly=True,
        help="Discount scheme applied to this document. Only one scheme can "
        "be active at a time; remove the discount to switch.",
    )
    discount_methods_available = fields.Boolean(
        compute="_compute_discount_methods_available",
        help="Technical: whether the company lets anybody apply some discount "
        "method. The Discount button is hidden when none is allowed.",
    )
    global_discount_type = fields.Selection(
        [("percent", "Percentage"), ("amount", "Fixed Amount")],
        string="Global Discount Type",
        copy=True,
        readonly=True,
    )
    global_discount_percent = fields.Float(
        string="Global Discount (%)", digits="Discount", copy=True, readonly=True
    )
    global_discount_amount = fields.Float(
        string="Global Discount Amount",
        digits="Product Price",
        copy=True,
        readonly=True,
    )

    discount_approval_state = fields.Selection(
        [
            ("exceeds", "Exceeds the Maximum"),
            ("to_approve", "To Approve"),
            ("approved", "Approved"),
        ],
        string="Discount Approval",
        copy=False,
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Hooks implemented by each model
    # ------------------------------------------------------------------
    def _discount_lines(self):
        """Product lines the discount applies to."""
        raise NotImplementedError

    def _discount_line_gross(self, line):
        """price_unit * quantity of a discountable line."""
        raise NotImplementedError

    def _discount_is_editable(self):
        """Whether the discount can still be changed on this document."""
        raise NotImplementedError

    def _discount_sync_stage(self, approval_state):
        """Hook: documents with a stage of their own for 'To Approve' (the
        sale order) move to / from it when the approval state changes."""

    @api.depends(
        "company_id.discount_method_limit_enabled",
        "company_id.discount_allow_line_percent",
        "company_id.discount_allow_line_amount",
        "company_id.discount_allow_global_subtotal",
        "company_id.discount_allow_global_total",
    )
    def _compute_discount_methods_available(self):
        wizard = self.env["l10n_ve.discount.wizard"]
        for document in self:
            document.discount_methods_available = bool(
                wizard.with_company(document.company_id)._allowed_schemes()
            )

    def action_open_discount_wizard(self):
        self.ensure_one()
        return {
            "name": _("Discount"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_ve.discount.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    # ------------------------------------------------------------------
    # Scheme helpers
    # ------------------------------------------------------------------
    def _get_doc_discount_type(self):
        """'percent' or 'amount': what the discount columns of the lines
        show. Without a scheme the company setting decides."""
        self.ensure_one()
        mode = self.discount_mode
        if mode == "line_amount":
            return "amount"
        if mode == "line_percent":
            return "percent"
        if mode == "global_subtotal":
            return self.global_discount_type or "percent"
        if mode == "global_total":
            return "percent"
        return self._get_discount_type_from_lines()

    def _get_discount_type_from_lines(self):
        """Document without a scheme: the discount its lines already hold wins,
        so documents saved before the schemes existed keep showing (and
        keeping) the discount they carry whatever the company setting is
        today. Without any discount the company setting decides."""
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Price")
        lines = self._discount_lines()
        if any(not float_is_zero(line.discount_fixed, precision_digits=precision) for line in lines):
            return "amount"
        if any(not float_is_zero(line.discount, precision_digits=precision) for line in lines):
            return "percent"
        return self.company_id.discount_type or "percent"

    def _get_global_total_discount(self, total_before, currency):
        """Amount of the global discount over the total, in the document
        currency. The taxes are untouched: it only lowers what is paid."""
        self.ensure_one()
        if self.discount_mode != "global_total" or currency.is_zero(total_before):
            return 0.0
        if self.global_discount_type == "percent":
            amount = total_before * self.global_discount_percent / 100.0
        else:
            amount = min(self.global_discount_amount, total_before)
        return currency.round(amount)

    def _discount_write_lines(self, lines, vals):
        with discount_apply(self.env):
            return lines.write(vals)

    def _discount_write_doc(self, vals):
        with discount_apply(self.env):
            return self.write(vals)

    def _check_discount_fields_protected(self, vals):
        """The scheme, the global discount and the approval state only change
        through the Discount button and the approve/reject actions: writing
        them directly (RPC) would skip the limits, the allowed methods and the
        approver permission. Server code (sudo) is trusted."""
        if self.env.su or is_discount_applying(self.env):
            return
        if any(field in vals for field in PROTECTED_DISCOUNT_FIELDS):
            raise AccessError(
                _(
                    "The discount scheme and its approval can only be changed "
                    "with the Discount button."
                )
            )

    def _discount_reset_values(self):
        return {
            "discount_mode": False,
            "global_discount_type": False,
            "global_discount_percent": 0.0,
            "global_discount_amount": 0.0,
        }

    def _discount_guard(self, vals):
        """Called before a line write/create that touches a discount field.

        Once the wizard set a scheme on the document, a line discount of
        another kind is refused. Without a scheme nothing changes: the
        company's discount type decides, as it always did.
        """
        if is_discount_applying(self.env):
            return
        self.ensure_one()
        rounding = self.env["decimal.precision"].precision_get("Product Price")
        wants_percent = bool(vals.get("discount")) and not float_is_zero(
            vals["discount"], precision_digits=rounding
        )
        wants_amount = bool(vals.get("discount_fixed")) and not float_is_zero(
            vals["discount_fixed"], precision_digits=rounding
        )
        if not (wants_percent or wants_amount):
            return
        if wants_percent:
            self._check_discount_method_allowed("lines", "percent")
        if wants_amount:
            self._check_discount_method_allowed("lines", "amount")
        mode = self.discount_mode
        if mode in GLOBAL_MODES:
            raise UserError(
                _(
                    "A global discount is applied to this document. Remove it "
                    "before discounting individual lines."
                )
            )
        if mode == "line_percent" and wants_amount and not wants_percent:
            raise UserError(
                _(
                    "This document uses percentage discounts on its lines. "
                    "Remove the discount before using a fixed amount."
                )
            )
        if mode == "line_amount" and wants_percent and not wants_amount:
            raise UserError(
                _(
                    "This document uses fixed amount discounts on its lines. "
                    "Remove the discount before using a percentage."
                )
            )

    def _check_discount_not_deductible(self):
        """A deductible document carries no discount (`l10n_ve_deductible`
        spreads its own amount over the lines): while the deductible is in
        use no discount can be applied. The deductible refuses the other
        way round (`_get_deductible_issues`)."""
        self.ensure_one()
        if "is_deductible" in self._fields and self.is_deductible:
            raise UserError(
                _(
                    "This document is deductible, so it cannot have a discount. "
                    "Turn off the deductible before applying a discount."
                )
            )

    # ------------------------------------------------------------------
    # Limits and approval
    # ------------------------------------------------------------------
    def _check_discount_method_allowed(self, scheme, discount_type):
        self.ensure_one()
        company = self.company_id
        if not company.discount_method_limit_enabled:
            return
        allowed = {
            ("lines", "percent"): company.discount_allow_line_percent,
            ("lines", "amount"): company.discount_allow_line_amount,
            ("global_subtotal", "percent"): company.discount_allow_global_subtotal,
            ("global_subtotal", "amount"): company.discount_allow_global_subtotal,
            ("global_total", "percent"): company.discount_allow_global_total,
            ("global_total", "amount"): company.discount_allow_global_total,
        }
        if not allowed.get((scheme, discount_type)):
            raise UserError(
                _(
                    "This discount method is not allowed by the company "
                    "settings, so nobody can apply it."
                )
            )

    def _discount_effective_percent(self):
        """(percentage applied, maximum allowed) of the document's scheme.
        Fixed amounts are compared as the % of the amount they discount."""
        self.ensure_one()
        company = self.company_id
        mode = self.discount_mode
        lines = self._discount_lines()
        if mode == "global_total":
            if self.global_discount_type == "percent":
                pct = self.global_discount_percent
            else:
                total = self.amount_untaxed + self.amount_tax
                pct = (
                    0.0
                    if self.currency_id.is_zero(total)
                    else self.global_discount_amount / total * 100
                )
            return pct, company.discount_max_global_total
        if mode == "global_subtotal":
            if self.global_discount_type == "percent":
                pct = self.global_discount_percent
            else:
                gross = sum(self._discount_line_gross(line) for line in lines)
                pct = (
                    0.0
                    if self.currency_id.is_zero(gross)
                    else self.global_discount_amount / gross * 100
                )
            return pct, company.discount_max_global_subtotal
        # Line schemes, or discounts typed by hand without a scheme.
        if self._get_doc_discount_type() == "amount":
            values = [line._get_exact_discount_percentage() for line in lines]
        else:
            values = [line.discount for line in lines]
        return (max(values) if values else 0.0), company.discount_max_line

    def _evaluate_discount_approval(self):
        """Compares the discount with the company maximum. Applying a discount
        never moves the document: within the limit nothing happens; above it
        an approver is never stopped, anybody else only gets the document marked
        as 'Exceeds the Maximum' (the approval stage comes when the document is
        confirmed). With the approval off, exceeding the maximum is an error."""
        for doc in self:
            company = doc.company_id
            if not (
                company.discount_max_limit_enabled
                and doc._discount_is_editable()
            ):
                if doc.discount_approval_state:
                    doc._discount_write_doc({"discount_approval_state": False})
                doc._discount_sync_stage(False)
                continue
            percent, limit = doc._discount_effective_percent()
            precision = self.env["decimal.precision"].precision_get("Discount")
            if (
                float_compare(percent, limit, precision_digits=precision) <= 0
                or doc._discount_covered_by_origin(percent)
            ):
                state = False
            elif company.discount_approval_enabled:
                # Approvers exist only while the approval is on: they are never
                # stopped. A document already waiting for approval keeps waiting.
                if self.env.user.has_group(APPROVER_GROUP):
                    state = False
                elif doc.discount_approval_state == "to_approve":
                    state = "to_approve"
                else:
                    state = "exceeds"
            else:
                raise UserError(
                    _(
                        "The discount (%(applied)s%%) exceeds the maximum allowed (%(limit)s%%).",
                        applied=round(percent, 2),
                        limit=limit,
                    )
                )
            if doc.discount_approval_state != state:
                doc._discount_write_doc({"discount_approval_state": state})
            if not state:
                doc._discount_sync_stage(False)

    def _discount_covered_by_origin(self, percent):
        """Hook: whether the discount was already approved upstream (an invoice
        whose sale order was confirmed with that same discount), so it does not
        ask for the approval again."""
        return False

    def _reset_discount_approval(self):
        """A document that goes back to draft starts its approval over: the old
        approval (or the old wait) does not count any more, so confirming it
        again with an excess goes to the approval stage again."""
        for doc in self:
            doc._discount_write_doc({"discount_approval_state": False})
            doc._close_discount_approval_activities()
            try:
                doc._evaluate_discount_approval()
            except UserError:
                # approval turned off meanwhile: going back must not be blocked
                pass

    # fields the approval lock leaves alone (the chatter, the stage itself)
    APPROVAL_LOCK = "discount_approval_state == 'to_approve'"
    APPROVAL_LOCK_SKIP = {
        "message_ids",
        "message_follower_ids",
        "activity_ids",
        "discount_approval_state",
        "discount_mode",
        "discount_type",
        "discount_methods_available",
    }
    APPROVAL_LOCK_BUTTONS = ("action_open_discount_wizard",)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        """The form is read-only in the approval stage: every field (and the
        lines, and the Discount button) gets the stage as one more reason to be
        read-only / hidden."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            self._lock_arch_for_approval(arch)
        return arch, view

    @api.model
    def _lock_arch_for_approval(self, arch):
        def merge(node, attribute, nested, lock=None):
            condition = ("parent." if nested else "") + (lock or self.APPROVAL_LOCK)
            existing = (node.get(attribute) or "").strip()
            if existing.lower() in ("1", "true"):
                return
            if existing and existing.lower() not in ("0", "false"):
                node.set(attribute, "(%s) or %s" % (existing, condition))
            else:
                node.set(attribute, condition)

        if arch.find(".//field[@name='discount_approval_state']") is None:
            etree.SubElement(arch, "field", name="discount_approval_state", invisible="1")
        if arch.find(".//field[@name='discount_methods_available']") is None:
            etree.SubElement(arch, "field", name="discount_methods_available", invisible="1")
        def is_read_only_by_nature(node):
            """A field that is already read-only in the model (computed without
            inverse, related...) must not get a `readonly` expression: a false
            expression would turn it editable."""
            model = self
            for parent in reversed(list(node.iterancestors("field"))):
                field = model._fields.get(parent.get("name"))
                if field is None or not field.relational:
                    return False
                model = self.env[field.comodel_name]
            field = model._fields.get(node.get("name"))
            return bool(field is not None and field.readonly)

        for node in arch.iter("field"):
            if node.get("name") in self.APPROVAL_LOCK_SKIP:
                continue
            if is_read_only_by_nature(node):
                continue
            nested = any(parent.tag == "field" for parent in node.iterancestors())
            merge(node, "readonly", nested)
        for name in self.APPROVAL_LOCK_BUTTONS:
            for button in arch.xpath("//button[@name='%s']" % name):
                nested = any(parent.tag == "field" for parent in button.iterancestors())
                merge(button, "invisible", nested)
        for button in arch.xpath("//button[@name='action_open_discount_wizard']"):
            nested = any(parent.tag == "field" for parent in button.iterancestors())
            merge(button, "invisible", nested, "not discount_methods_available")

    def _discount_approvers(self):
        """Active internal users of the company with the approval permission."""
        self.ensure_one()
        group = self.env.ref(APPROVER_GROUP)
        users = self.env["res.users"].sudo().search(
            [("all_group_ids", "in", group.ids), ("share", "=", False)]
        )
        return users.filtered(lambda user: self.company_id in user.company_ids)

    def _send_to_approval(self):
        """Confirming a document that exceeds the maximum does not confirm it:
        it goes to the approval stage, where an approver decides. Every approver
        is told inside Odoo; with nobody to approve it the document cannot enter
        the stage, so it would never leave it."""
        approvers = {doc.id: doc._discount_approvers() for doc in self}
        for doc in self:
            if not approvers[doc.id]:
                raise UserError(
                    _(
                        "The discount approval is active but there is no discount "
                        "approver assigned. Give the permission \"Approve Excess "
                        "Discounts\" to a user before sending a discount to approval."
                    )
                )
        for doc in self:
            percent, limit = doc._discount_effective_percent()
            doc._discount_write_doc({"discount_approval_state": "to_approve"})
            doc._discount_sync_stage("to_approve")
            doc._notify_discount_approvers(approvers[doc.id], percent, limit)

    def _notify_discount_approvers(self, approvers, percent, limit):
        """A message in the chatter addressed to every approver (their Odoo
        inbox) and a notification on screen for those who are connected."""
        self.ensure_one()
        body = _(
            "%(document)s is waiting for the approval of its discount: %(applied)s%% "
            "against a maximum of %(limit)s%%.",
            document=self.display_name,
            applied=round(percent, 2),
            limit=limit,
        )
        self.message_post(
            body=body,
            partner_ids=approvers.partner_id.ids,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
        )
        for user in approvers:
            # a to-do in the Activities of the approver: it stays there until the
            # discount is approved, rejected or the document goes back
            self.activity_schedule(
                DISCOUNT_APPROVAL_ACTIVITY,
                summary=_("Approve the discount of %s", self.display_name),
                note=body,
                user_id=user.id,
            )
            self.env["bus.bus"]._sendone(
                user.partner_id,
                "simple_notification",
                {
                    "type": "warning",
                    "title": _("Discount approval"),
                    "message": body,
                    "sticky": True,
                },
            )

    def _discount_approval_notification(self):
        """What the confirm button answers when the document went to approval."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "title": _("Discount approval"),
                "message": _(
                    "The discount exceeds the maximum allowed: the document is now "
                    "waiting for a discount approver."
                ),
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def _check_discount_approved(self):
        """A document waiting for approval, or that still exceeds the maximum,
        cannot go on by any path."""
        for doc in self:
            if doc.discount_approval_state in ("exceeds", "to_approve"):
                raise UserError(
                    _("The discount of this document is waiting for approval.")
                )

    def _discount_owners(self):
        """Users to tell about the decision on the discount: the salesperson of
        the document and whoever created it (hook, implemented by each model)."""
        self.ensure_one()
        return self.env["res.users"]

    def _notify_discount_owners(self, decision):
        """Tells the owner of the document (inside Odoo: a message addressed to
        them in the chatter and a notification on screen) that its discount was
        approved or rejected. The one deciding is not notified."""
        self.ensure_one()
        owners = (self._discount_owners() - self.env.user).filtered(
            lambda user: user.active and not user.share
        )
        if decision == "approved":
            title = _("Discount approved")
            body = _(
                "The discount of %(document)s was approved by %(user)s.",
                document=self.display_name,
                user=self.env.user.name,
            )
            level = "success"
        else:
            title = _("Discount rejected")
            body = _(
                "The discount of %(document)s was rejected by %(user)s and removed.",
                document=self.display_name,
                user=self.env.user.name,
            )
            level = "danger"
        self.message_post(
            body=body,
            partner_ids=owners.partner_id.ids,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
        )
        for user in owners:
            self.env["bus.bus"]._sendone(
                user.partner_id,
                "simple_notification",
                {"type": level, "title": title, "message": body, "sticky": True},
            )

    def _close_discount_approval_activities(self):
        """The to-dos of the approvers are gone once the wait is over."""
        self.sudo().activity_unlink([DISCOUNT_APPROVAL_ACTIVITY])

    def _discount_after_approval(self):
        """Hook: what an approved document does next (the natural next step of
        its own flow): the order is confirmed, the invoice is posted."""

    def action_approve_discount(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_("Only a discount approver can approve this discount."))
        approved = self.filtered(lambda d: d.discount_approval_state == "to_approve")
        for doc in approved:
            doc._discount_write_doc({"discount_approval_state": "approved"})
            doc._discount_sync_stage("approved")
            doc._close_discount_approval_activities()
            doc._notify_discount_owners("approved")
        return approved._discount_after_approval()

    def action_reject_discount(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_("Only a discount approver can reject this discount."))
        for doc in self.filtered(lambda d: d.discount_approval_state == "to_approve"):
            doc._clear_discount()
            doc._discount_write_doc({"discount_approval_state": False})
            doc._close_discount_approval_activities()
            doc._notify_discount_owners("rejected")

    # ------------------------------------------------------------------
    # Applying / removing a discount
    # ------------------------------------------------------------------
    def _apply_discount(self, scheme, discount_type, value):
        """Applies a discount to the whole document.

        :param scheme: 'lines' (same discount on every line), 'global_subtotal'
            or 'global_total'.
        :param discount_type: 'percent' or 'amount'.
        :param value: the percentage or the amount.
        """
        self.ensure_one()
        if not self._discount_is_editable():
            raise UserError(_("The discount cannot be changed on this document."))
        if scheme not in ("lines", "global_subtotal", "global_total"):
            raise UserError(_("Unknown discount scheme."))
        if discount_type not in ("percent", "amount"):
            raise UserError(_("Unknown discount type."))
        self._check_discount_not_deductible()
        self._check_discount_method_allowed(scheme, discount_type)
        lines = self._discount_lines()
        if not lines:
            raise UserError(_("Add at least one product line before applying a discount."))
        precision = self.env["decimal.precision"].precision_get("Product Price")
        if float_compare(value, 0.0, precision_digits=precision) <= 0:
            raise UserError(_("The discount must be greater than zero."))
        if discount_type == "percent" and float_compare(value, 100.0, precision_digits=precision) > 0:
            raise UserError(_("The discount percentage cannot exceed 100."))
        total_gross = sum(self._discount_line_gross(line) for line in lines)
        if (
            discount_type == "amount"
            and scheme != "global_total"
            and float_compare(value, total_gross, precision_digits=precision) >= 0
        ):
            raise UserError(
                _("The discount amount must be less than the subtotal (%s).", total_gross)
            )
        self._clear_discount()
        is_global = scheme != "lines"
        if scheme == "lines":
            mode = "line_percent" if discount_type == "percent" else "line_amount"
        else:
            mode = scheme
        self._discount_write_doc(
            {
                "discount_mode": mode,
                "global_discount_type": discount_type if is_global else False,
                "global_discount_percent": value
                if is_global and discount_type == "percent"
                else 0.0,
                "global_discount_amount": value
                if is_global and discount_type == "amount"
                else 0.0,
            }
        )
        if mode != "global_total":
            self._distribute_discount(lines, discount_type, value)
        self._evaluate_discount_approval()

    def _distribute_discount(self, lines, discount_type, value):
        """Writes the discount on the lines: the same % on each, or a fixed
        amount split in proportion to the line subtotals (shared spreading of
        `l10n_ve_invoice`, the same one the deductible uses)."""
        if discount_type == "percent":
            self._discount_write_lines(lines, {"discount": value, "discount_fixed": 0.0})
            return
        gross = {line: self._discount_line_gross(line) for line in lines}
        gross = {line: amount for line, amount in gross.items() if amount > 0}
        if not gross:
            return
        shares = spread_amount(value, gross, self.currency_id.rounding)
        for line, share in shares.items():
            self._discount_write_lines(line, {"discount_fixed": share, "discount": 0.0})

    def _clear_discount(self):
        """Zeroes every line discount and forgets the scheme."""
        self.ensure_one()
        self._discount_write_doc(
            dict(self._discount_reset_values(), discount_approval_state=False)
        )
        self._discount_sync_stage(False)
        lines = self._discount_lines()
        if lines:
            self._discount_write_lines(lines, {"discount": 0.0, "discount_fixed": 0.0})

    def _remove_discount(self):
        for doc in self:
            if not doc._discount_is_editable():
                raise UserError(_("The discount cannot be changed on this document."))
            doc._clear_discount()

    def _reapply_global_discount(self):
        """Keeps the discount consistent after the lines changed: a global
        discount over the subtotal covers new lines and follows price or
        quantity changes, and any scheme is dropped once no product line is
        left."""
        for doc in self:
            if not doc.discount_mode or is_discount_applying(self.env):
                continue
            lines = doc._discount_lines()
            if not lines:
                doc._discount_write_doc(doc._discount_reset_values())
            elif doc.discount_mode == "global_subtotal":
                value = (
                    doc.global_discount_percent
                    if doc.global_discount_type == "percent"
                    else doc.global_discount_amount
                )
                doc._distribute_discount(lines, doc.global_discount_type, value)

    def copy(self, default=None):
        # The copy keeps the scheme; its lines carry the discount already.
        with discount_apply(self.env):
            return super().copy(default)
