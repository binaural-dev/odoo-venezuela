from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class AccountMoveRetention(models.Model):
    _inherit = "account.move"

    base_currency_is_vef = fields.Boolean(
        compute="_compute_currency_fields",
    )

    apply_islr_retention = fields.Boolean(
        string="Apply ISLR Retention?",
        default=False,
    )

    islr_voucher_number = fields.Char(copy=False)

    iva_voucher_number = fields.Char(copy=False)

    municipal_voucher_number = fields.Char(copy=False)

    retention_islr_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="ISLR Retention Lines",
        domain=[
            "|",
            ("payment_concept_id", "!=", False),
            ("retention_id.type_retention", "=", "islr"),
        ],
    )

    retention_iva_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="IVA Retention Lines",
        domain=[("retention_id.type_retention", "=", "iva")],
    )

    retention_municipal_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="Municipal Retention Lines",
        domain=[
            "|",
            ("economic_activity_id", "!=", False),
            ("retention_id.type_retention", "=", "municipal"),
        ],
    )

    generate_iva_retention = fields.Boolean(
        string="Generate IVA Retention?",
        default=False,
    )

    is_third_party_retention = fields.Boolean(
        string="Third Party Billing",
        default=False,
        help="Enable to create retentions on behalf of a third-party provider.",
    )

    third_party_iva_retention_count = fields.Integer(
        string="Third Party IVA Retentions",
        compute="_compute_third_party_retention_counts",
    )

    third_party_islr_retention_count = fields.Integer(
        string="Third Party ISLR Retentions",
        compute="_compute_third_party_retention_counts",
    )

    not_edit_municipal_retention_lines = fields.Boolean(
        string="Edit Municipal Retention Lines?",
        compute="_compute_state_retentions_lines",
    )

    not_edit_islr_retention_lines = fields.Boolean(
        string="Edit ISLR Retention Lines?", compute="_compute_state_retentions_lines"
    )

    def _compute_third_party_retention_counts(self):
        Retention = self.env["account.retention"]
        for record in self:
            if record.id and record.is_third_party_retention:
                record.third_party_iva_retention_count = Retention.search_count([
                    ("retention_line_ids.move_id", "=", record.id),
                    ("type_retention", "=", "iva"),
                    ("is_third_party_retention", "=", True),
                ])
                record.third_party_islr_retention_count = Retention.search_count([
                    ("retention_line_ids.move_id", "=", record.id),
                    ("type_retention", "=", "islr"),
                    ("is_third_party_retention", "=", True),
                ])
            else:
                record.third_party_iva_retention_count = 0
                record.third_party_islr_retention_count = 0

    def action_view_third_party_iva_retentions(self):
        self.ensure_one()
        retentions = self.env["account.retention"].search([
            ("retention_line_ids.move_id", "=", self.id),
            ("type_retention", "=", "iva"),
            ("is_third_party_retention", "=", True),
        ])
        if len(retentions) == 0 and self.state != "posted":
            raise UserError(_("You cannot create retentions for a draft or cancelled invoice."))

        iva_form = self.env.ref(
            "l10n_ve_payment_extension.view_retention_iva_form_l10n_ve_payment_extension"
        )
        iva_list = self.env.ref(
            "l10n_ve_payment_extension.view_retention_iva_list_l10n_ve_payment_extension"
        )
        action = {
            "name": _("Third Party IVA Retentions"),
            "type": "ir.actions.act_window",
            "res_model": "account.retention",
            "views": [(iva_list.id, "list"), (iva_form.id, "form")],
            "context": {
                "default_type": "in_invoice",
                "default_type_retention": "iva",
                "default_available_invoice_ids": [Command.set([self.id])],
                "default_retention_line_ids": [Command.create({"move_id": self.id})],
                "default_is_third_party_retention": True,
            },
        }
        if len(retentions) == 0:
            action["views"] = [(iva_form.id, "form")]
        else:
            action["domain"] = [("id", "in", retentions.ids), ("is_third_party_retention", "=", True)]
            
        if self.state != "posted":
            action["context"].update({"create": False, "edit": False})
        return action

    def action_view_third_party_islr_retentions(self):
        self.ensure_one()
        retentions = self.env["account.retention"].search([
            ("retention_line_ids.move_id", "=", self.id),
            ("type_retention", "=", "islr"),
            ("is_third_party_retention", "=", True),
        ])
        if len(retentions) == 0 and self.state != "posted":
            raise UserError(_("You cannot create retentions for a draft or cancelled invoice."))

        islr_form = self.env.ref(
            "l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension"
        )
        action = {
            "name": _("Third Party ISLR Retentions"),
            "type": "ir.actions.act_window",
            "res_model": "account.retention",
            "views": [(False, "list"), (islr_form.id, "form")],
            "context": {
                "default_type": "in_invoice",
                "default_type_retention": "islr",
                "default_available_invoice_ids": [Command.set([self.id])],
                "default_retention_line_ids": [Command.create({"move_id": self.id})],
                "default_is_third_party_retention": True,
            },
        }
        if len(retentions) == 0:
            action["views"] = [(islr_form.id, "form")]
        else:
            action["domain"] = [("id", "in", retentions.ids), ("is_third_party_retention", "=", True)]
            
        if self.state != "posted":
            action["context"].update({"create": False, "edit": False})
        return action

    @api.depends(
        "retention_islr_line_ids.state",
        "retention_iva_line_ids.state",
        "retention_municipal_line_ids.state",
    )
    def _compute_state_retentions_lines(self):
        for record in self:
            edit_islr_retention_lines = record.retention_islr_line_ids.filtered(
                lambda l: l.state == "emitted"
            )
            edit_municipal_retention_lines = (
                record.retention_municipal_line_ids.filtered(
                    lambda l: l.state == "emitted"
                )
            )
            record.not_edit_islr_retention_lines = bool(
                edit_islr_retention_lines)
            record.not_edit_municipal_retention_lines = bool(
                edit_municipal_retention_lines
            )

    def _compute_currency_fields(self):
        for retention in self:
            retention.base_currency_is_vef = (
                self.env.company.currency_id == self.env.ref("base.VEF")
            )

    def write(self, vals):
        """
        Override the write method to recalculate municipal retentions if the invoice lines change.
        """
        res = super(AccountMoveRetention, self).write(vals)
        if "invoice_line_ids" in vals:
            for move in self:
                if (
                    move.move_type in ("in_invoice", "in_refund")
                    and move.retention_municipal_line_ids
                ):
                    for line in move.retention_municipal_line_ids:
                        line.onchange_economic_activity_id()
        return res

    def action_post(self):
        """
        Override the action_post method to create the retentions payment.
        """
        res = super().action_post()
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            company = move.company_id or self.env.company
            if (
                move.retention_islr_line_ids
                and not move.islr_voucher_number
                and move.retention_islr_line_ids.filtered(
                    lambda l: l.state != "emitted"
                )
            ):
                move._validate_islr_retention()
                retention = move._create_supplier_retention("islr")

                if not company.create_retentions_of_suppliers_in_draft:
                    retention.action_post()
                move.islr_voucher_number = retention.number

            if (
                move.retention_municipal_line_ids
                and not move.municipal_voucher_number
                and move.retention_municipal_line_ids.filtered(
                    lambda l: l.state != "emitted"
                )
            ):
                move._validate_municipal_retention()
                retention = move._create_supplier_retention("municipal")
                if not company.create_retentions_of_suppliers_in_draft:
                    retention.action_post()

            if (
                move.generate_iva_retention
                and not move.retention_iva_line_ids.filtered(
                    lambda l: l.state != "cancel"
                )
            ):
                move._validate_iva_retention()
                retention = move._create_supplier_retention("iva")
                if not company.create_retentions_of_suppliers_in_draft:
                    retention.action_post()
                move.iva_voucher_number = retention.number
        return res

    def _validate_islr_retention(self):
        """
        Validate that the company has a journal for ISLR supplier retention, the partner a type of
        person and that the amount of the retention is greater than zero, in order for the ISLR
        retention to be created.
        """
        self.ensure_one()
        if not self.env.company.islr_supplier_retention_journal_id:
            raise UserError(
                _("The company must have a journal for ISLR supplier retention.")
            )
        islr_retention = self.retention_islr_line_ids
        sum_invoice_amount = sum(
            islr_retention.filtered(lambda rl: rl.state != "cancel").mapped(
                "invoice_amount"
            )
        )
        if sum_invoice_amount > self.tax_totals.get("base_amount", 0.0):
            raise UserError(
                _(
                    "The amount of the retention is greater than the total amount of the invoice %s."
                )
            )
        sum_invoice_amount = sum(
            self.retention_islr_line_ids.filtered(
                lambda rl: rl.state != "cancel"
            ).mapped("invoice_amount")
        )
        self._check_retention_vs_move(islr_retention)

        if not self.partner_id.type_person_id:
            raise UserError(_("The partner must have a type of person"))
        if sum_invoice_amount <= 0:
            raise UserError(
                _("The amount of the retention must be greater than zero."))

    @api.model
    def _check_retention_vs_move(self, islr_retention_lines):
        for line in islr_retention_lines:
            move = line.move_id
            invoice_base = move.tax_totals.get("base_amount", 0.0)
            if line.invoice_amount > invoice_base:
                raise UserError(
                    _(
                        "The taxable base of one of the withholding lines is greater than the taxable base of the invoice"
                    )
                )

    def _validate_iva_retention(self):
        """
        Validate that the company has a journal for IVA supplier retention and that the invoice has
        at least one tax, in order for the IVA retention to be created.
        """
        self.ensure_one()
        if not self.env.company.iva_supplier_retention_journal_id:
            raise UserError(
                _("The company must have a journal for IVA supplier retention.")
            )
        if not any(
            self.invoice_line_ids.mapped(
                "tax_ids").filtered(lambda x: x.amount > 0)
        ):
            raise UserError(_("The invoice has no tax."))

    def _validate_municipal_retention(self):
        """
        Validate that the company has a journal for municipal supplier retention in order for the
        municipal retention to be created.
        """
        self.ensure_one()
        if not self.env.company.municipal_supplier_retention_journal_id:
            raise UserError(
                _("The company must have a journal for municipal supplier retention.")
            )

    @api.model
    def _create_supplier_retention(self, type_retention):
        """
        Calls the method to create the payment for the retention of the type specified in the
        type_retention parameter.

        Params
        ------
        invoice_id: account.move
            The invoice to which the retention will be applied.
        type_retention: tuple[str, str]
            The type of retention and the type of invoice.

        Returns
        -------
        account.retention
            The retention created.
        """
        self.ensure_one()
        if type_retention == "iva" and not self.partner_id.withholding_type_id:
            raise UserError(_("The partner has no withholding type."))

        retention = self.env["account.retention"]
        payment_type = "outbound"
        if self.move_type == "in_refund":
            payment_type = "inbound"

        journals = {
            "iva": self.env.company.iva_supplier_retention_journal_id,
            "islr": self.env.company.islr_supplier_retention_journal_id,
            "municipal": self.env.company.municipal_supplier_retention_journal_id,
        }

        Payment = self.env["account.payment"]
        Retention = self.env["account.retention"]
        payment_vals = {
            "payment_type": payment_type,
            "partner_type": "supplier",
            "partner_id": self.partner_id.id,
            "journal_id": journals[type_retention].id,
            "payment_type_retention": type_retention,
            "payment_method_id": self.env.ref(
                "account.account_payment_method_manual_in"
            ).id,
            "is_retention": True,
            "foreign_rate": self.foreign_rate,
            "foreign_inverse_rate": self.foreign_inverse_rate,
            "currency_id": self.env.user.company_id.currency_id.id,
        }
        if 'subsidiary' in self.env.company._fields:
                if self.env.company.subsidiary:
                    payment_vals['account_analytic_id'] = self.account_analytic_id.id
                else:
                    payment_vals['account_analytic_id'] = False
        if type_retention == "islr":
            payment_vals["retention_line_ids"] = self.retention_islr_line_ids.filtered(
                lambda rl: rl.state != "cancel"
            ).ids
        elif type_retention == "municipal":
            payment_vals["retention_line_ids"] = (
                self.retention_municipal_line_ids.filtered(
                    lambda rl: rl.state != "cancel"
                ).ids
            )

        payment = Payment.create(payment_vals)
        retention_vals = {
            "payment_ids": [Command.link(payment.id)],
            "date_accounting": self.date,
            "date": self.date if self.move_type == "in_invoice" else False,
            "type_retention": type_retention,
            "type": "in_invoice",
            "partner_id": self.partner_id.id,
        }

        if type_retention == "iva":
            retention_lines_data = Retention.compute_retention_lines_data(
                self, payment)
            retention_vals["retention_line_ids"] = [
                Command.create(line) for line in retention_lines_data
            ]
        elif type_retention == "islr":
            retention_vals["retention_line_ids"] = (
                self.retention_islr_line_ids.filtered(
                    lambda rl: rl.state != "cancel"
                ).ids
            )
        else:
            retention_vals["retention_line_ids"] = (
                self.retention_municipal_line_ids.filtered(
                    lambda rl: rl.state != "cancel"
                ).ids
            )

        retention = Retention.create(retention_vals)
        payment.compute_retention_amount_from_retention_lines()
        return retention

    def action_register_payment(self):
        """
        Override the action_register_payment method to send the is_out_invoice context to the
        payment wizard.

        This is used to know if the invoice is an outgoing invoice, in order to know if the
        option to create a retention should be displayed in the payment wizard.
        """
        res = super().action_register_payment()
        res["context"]["default_is_out_invoice"] = any(
            self.filtered(lambda i: i.move_type in (
                "out_invoice", "out_refund"))
        )
        return res

    @api.depends("move_type", "line_ids.amount_residual")
    def _compute_payments_widget_reconciled_info(self):
        res = super()._compute_payments_widget_reconciled_info()
        for record in self:
            if not record.invoice_payments_widget:
                continue

            for payment in record.invoice_payments_widget.get("content"):
                if not payment.get("account_payment_id", False):
                    payment["is_retention"] = False
                    continue
                payment_id = self.env["account.payment"].browse(
                    payment["account_payment_id"]
                )
                payment["is_retention"] = payment_id.is_retention

        return res

    @api.model
    def validate_payment(self, payment):
        """This function is used to not add withholding in the calculation of the last payment date"""
        if payment.get("is_retention", False):
            return False
        return True

    @api.model
    def _compute_rate_for_documents(self, documents, is_sale):
        res = super()._compute_rate_for_documents(documents, is_sale)
        for move in documents:
            if move.origin_payment_id.is_retention:
                move.foreign_rate = move.origin_payment_id.foreign_rate
                move.foreign_inverse_rate = move.origin_payment_id.foreign_rate
        return res
