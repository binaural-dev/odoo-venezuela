from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools import float_compare
from collections import defaultdict
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
            "&", 
            ("retention_id.state", "!=", "cancel"),
            "|",
            ("payment_concept_id", "!=", False),
            ("retention_id.type_retention", "=", "islr"),
        ],
    )

    retention_iva_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="IVA Retention Lines",
        domain=[("retention_id.type_retention", "=", "iva"),
            ("retention_id.state", "!=", "cancel")],
    )

    retention_municipal_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="Municipal Retention Lines",
        domain=[
            "&", 
            ("retention_id.state", "!=", "cancel"),
            "|",
            ("economic_activity_id", "!=", False),
            ("retention_id.type_retention", "=", "municipal"),
        ],
    )

    generate_iva_retention = fields.Boolean(
        string="Generate IVA Retention?",
        default=False,
        copy=False
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

    is_isrl_retention_available = fields.Boolean(
        string="¿Is retention islr Available?", compute="_compute_retention_islr_avalability", store=True,copy=False
    )

    generate_islr_retention = fields.Boolean(
        string="¿Generate ISLR Retention?",
        default=False, copy=False
    )

    count_islr_retention = fields.Integer('count islr retention',compute="compute_count_retentions")
    count_iva_retention = fields.Integer('count iva retention',compute="compute_count_retentions")
    count_municipal_retention = fields.Integer('count iva retention', compute="compute_count_retentions")

    has_emited_islr_retention = fields.Boolean('has emited islr_retention', compute="compute_count_retentions")
    has_emited_municipal_retention = fields.Boolean('has emited municipal retention', compute="compute_count_retentions")
    has_emited_iva_retention = fields.Boolean('has emited iva retention', compute="compute_count_retentions")

    has_pending_retention_to_cancel = fields.Boolean(
        string="Has Pending Retention To Cancel",
        compute="_compute_has_pending_retention_to_cancel",
    )

    retention_resync_pending = fields.Boolean(
        string="Retention Resync Pending",
        compute="_compute_retention_resync_pending",
        help=(
            "True when this invoice has an emitted retention whose lines or"
            " linked payment no longer match what would be recalculated"
            " from the invoice's current data (e.g. the invoice was reset"
            " to draft, edited and reposted)."
        ),
    )

    @api.depends(
        "move_type",
        "retention_islr_line_ids.retention_id.state",
        "retention_iva_line_ids.retention_id.state",
        "retention_municipal_line_ids.retention_id.state",
    )
    def _compute_has_pending_retention_to_cancel(self):
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                move.has_pending_retention_to_cancel = False
                continue
            retentions = (
                move.retention_islr_line_ids
                | move.retention_iva_line_ids
                | move.retention_municipal_line_ids
            ).mapped("retention_id").filtered(lambda r: r.state != "cancel")
            move.has_pending_retention_to_cancel = bool(retentions)

    @api.depends(
        "state",
        "move_type",
        "invoice_line_ids.tax_ids",
        "invoice_line_ids.product_id",
        "invoice_line_ids.balance",
        "retention_islr_line_ids.invoice_amount",
        "retention_islr_line_ids.foreign_invoice_amount",
        "retention_islr_line_ids.retention_amount",
        "retention_islr_line_ids.state",
        "retention_iva_line_ids.invoice_amount",
        "retention_iva_line_ids.foreign_invoice_amount",
        "retention_iva_line_ids.retention_amount",
        "retention_iva_line_ids.state",
        "retention_municipal_line_ids.invoice_amount",
        "retention_municipal_line_ids.foreign_invoice_amount",
        "retention_municipal_line_ids.retention_amount",
        "retention_municipal_line_ids.state",
    )
    def _compute_retention_resync_pending(self):
        for move in self:
            move.retention_resync_pending = bool(move._get_retentions_pending_resync())

    def compute_count_retentions(self):
        
        for rec in self:
            lines = self.env['account.retention.line'].search([('move_id', 'in', rec.ids),("retention_id.state", "!=", "cancel")])
            ret_all = lines.filtered(lambda l: l.move_id.id == rec.id).mapped('retention_id')

            islr = ret_all.filtered(lambda r: r.type_retention == 'islr')
            iva = ret_all.filtered(lambda r: r.type_retention == 'iva')
            muni = ret_all.filtered(lambda r: r.type_retention == 'municipal')
            
            rec.count_islr_retention = len(islr)
            rec.has_emited_islr_retention = any(r.state == 'emitted' for r in islr)
            rec.count_iva_retention = len(iva)
            rec.has_emited_iva_retention = any(r.state == 'emitted' for r in iva)
            rec.count_municipal_retention = len(muni)
            rec.has_emited_municipal_retention = any(r.state == 'emitted' for r in muni)

    def action_view_retention(self):
        self.ensure_one()
        ret_type = self.env.context.get('retention_type')
        
        retentions = False
        if ret_type == 'iva':
           retentions = self.retention_iva_line_ids.mapped('retention_id')
        elif ret_type == 'islr':
            retentions = self.retention_islr_line_ids.mapped('retention_id')
        else:
            retentions = self.retention_municipal_line_ids.mapped('retention_id')

        names = {
            'iva': _('IVA Retentions'),
            'islr': _('ISLR Retentions'),
            'municipal': _('Municipal Retentions'),
        }
        action_name = names.get(ret_type, _('Retentions'))

        if retentions:
            if len(retentions) == 1:
                
                return {
                    'name': action_name,
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.retention',
                    'view_mode': 'form',
                    'res_id': retentions.id,
                    'target': 'current',
                }
            else:
                return {
                    'name': action_name,
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.retention',
                    'view_mode': 'list,form',
                    'domain': [('id', 'in', retentions.ids)],
                    'target': 'current',
                }
        

    @api.depends(
        "invoice_line_ids",
        "invoice_line_ids.product_id",
        "invoice_line_ids.product_id.product_tmpl_id.payment_concept",
    )
    def _compute_retention_islr_avalability(self):
        for record in self:
            record.is_isrl_retention_available = any(
                line.product_id.product_tmpl_id.type == 'service' and 
                line.product_id.product_tmpl_id.payment_concept 
                for line in record.invoice_line_ids
            )

            if not record.is_isrl_retention_available and record.generate_islr_retention:
                record.generate_islr_retention = False

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
            if (not move.islr_voucher_number and move.generate_islr_retention ):
                move.auto_create_islr_retention()

            if (move.generate_iva_retention and not move.iva_voucher_number):
                move._validate_iva_retention()
                retention = move._create_retention("iva")
                if not move.company_id.create_retentions_of_suppliers_in_draft and move.move_type in ['in_invoice']:
                    retention.action_post()
                move.iva_voucher_number = retention.number

            if move.move_type not in ("in_invoice", "in_refund"):
                continue

            if (
                move.retention_municipal_line_ids
                and not move.municipal_voucher_number
                and move.retention_municipal_line_ids.filtered(
                    lambda l: l.state != "emitted"
                )
            ):
                move._validate_municipal_retention()
                retention = move._create_retention("municipal")
                if not move.company_id.create_retentions_of_suppliers_in_draft and move.move_type in ['in_invoice']:
                    retention.action_post()

            move._resync_retentions()

        return res

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

        is_supplier = self.move_type in ['in_invoice', 'in_refund']

        if is_supplier:
            if not self.env.company.iva_supplier_retention_journal_id:
                raise UserError(
                    _("The company must have a journal for IVA supplier retention.")
                )
        else:
            if not self.env.company.iva_customer_retention_journal_id:
                raise UserError(
                    _("The company must have a journal for IVA customer retention.")
                )
            
        if not any(
            self.invoice_line_ids.mapped(
                "tax_ids").filtered(lambda x: x.amount > 0)
        ):
            raise UserError(_("The invoice has no applicable taxes. IVA Retention cannot be generated."))

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


    def _get_retention_journals(self, is_supplier):
        if is_supplier:
            return {
                "iva": self.env.company.iva_supplier_retention_journal_id,
                "municipal": self.env.company.municipal_supplier_retention_journal_id,
            }
        else:
            return {
                "iva": self.env.company.iva_customer_retention_journal_id,
                "municipal": self.env.company.municipal_customer_retention_journal_id,
            }


    def _prepare_retention_vals(self, type_retention, payment=False):
        invoice_date = self.invoice_date_display or self.invoice_date
        today = fields.Date.context_today(self)
        date_accounting = max(self.date, invoice_date) if invoice_date else self.date
        retention_vals = {
            "date_accounting": min(date_accounting, today),
            "date": self.date,
            "type_retention": type_retention,
            "type": self.move_type, 
            "partner_id": self.partner_id.id,
        }
    
        # Validamos si existe el payment para agregarlo a los IDs de relación
        if payment:
            retention_vals["payment_ids"] = [Command.link(payment.id)]
    
        if type_retention == "iva":
            # Pasamos payment solo si existe, de lo contrario pasamos None o False según espere el método
            retention_lines_data = self.env["account.retention"].compute_retention_lines_data(self, payment or False)
            retention_vals["retention_line_ids"] = [
                Command.create(line) for line in retention_lines_data
            ]
        elif type_retention == "islr":
            retention_vals["retention_line_ids"] = self.retention_islr_line_ids.filtered(
                lambda rl: rl.state != "cancel"
            ).ids
        else:
            retention_vals["retention_line_ids"] = self.retention_municipal_line_ids.filtered(
                lambda rl: rl.state != "cancel"
            ).ids
    
        return retention_vals
    
    @api.model
    def _create_retention(self, type_retention):
        
        self.ensure_one()

        if type_retention == "iva" and not self.partner_id.withholding_type_id:
            raise UserError(_("The partner has no withholding type."))

        retention_vals = self._prepare_retention_vals(type_retention, False)
        retention = self.env["account.retention"].create(retention_vals)
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
        
    def action_create_islr_from_invoice(self):

        if len(self) > 1:
            return self._action_create_multi_islr_retention()
        self.ensure_one()
    
        for record in self:
            retentions = record.validate_islr()

            if retentions:
                if len(retentions) == 1:
                    return {
                        'name': _('ISLR Retention'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'account.retention',
                        'view_mode': 'form',
                        'res_id': retentions.id,
                        'target': 'current',
                    }
                else:
                    return {
                        'name': _('ISLR Retention'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'account.retention',
                        'view_mode': 'list,form',
                        'domain': [('id', 'in', retentions.ids)],
                        'target': 'current',
                    }
            
            payment_concepts = self._get_payment_concepts_from_invoice()
                        
            if record.move_type in ['in_invoice', 'in_refund']:
                xml_action_id = 'l10n_ve_payment_extension.action_retention_islr_supplier'
            elif record.move_type in ['out_invoice', 'out_refund']:
                xml_action_id = 'l10n_ve_payment_extension.action_retention_islr_client'
            else:
                raise UserError(_("This action is only valid for customer or vendor invoices."))


            action = self.env.ref(xml_action_id).read()[0]
            ctx = safe_eval(action.get('context', '{}'))
            ctx.update({
                'default_partner_id': record.partner_id.id,
                'default_invoice_id': record.id,
                'default_date_accounting': fields.Date.context_today(self),
                'default_type': record.move_type,
                'default_type_retention': 'islr',
                'default_islr_lines': payment_concepts,
            })

            action['context'] = ctx
            action['views'] = [(self.env.ref('l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension').id, 'form')]
            action['view_mode'] = 'form'
            action['target'] = 'current'
            
            return action
    
    def _get_payment_concepts_from_invoice(self):

        for rec in self:
            payment_concepts = []

            valid_lines = rec.invoice_line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id.type == 'service' and 
                        l.product_id.product_tmpl_id.payment_concept
            )
            use_price_unit = len(valid_lines) > 1

            for line in rec.invoice_line_ids:
                if line.product_id.product_tmpl_id.type == 'service' and bool(line.product_id.product_tmpl_id.payment_concept):
                    product_tmpl = line.product_id.product_tmpl_id
                    if product_tmpl.type == 'service' and product_tmpl.payment_concept:

                        concept_id = product_tmpl.payment_concept.id

                        # Task #82491 asks specifically for a supplier-side
                        # setting ("retención de ISLR Proveedores"); it must
                        # not silently change the base of client ISLR
                        # retentions, which nobody requested.
                        is_supplier_invoice = rec.move_type in ("in_invoice", "in_refund", "in_debit")
                        use_service_subtotal = use_price_unit or (
                            is_supplier_invoice
                            and self.env.company.islr_prioritize_product_subtotal_base
                        )

                        base_amount = (
                            abs(line.balance)
                            if use_service_subtotal
                            else abs(line.move_id.tax_totals["base_amount"])
                        )
                        payment_concepts.append((
                            concept_id,
                            base_amount,
                            line.id, 
                        ))
            return payment_concepts
        
    def auto_create_islr_retention(self):
        for rec in self:

            if not self.env.company.islr_supplier_retention_journal_id:
                raise UserError(
                    _("The company must have a journal for ISLR supplier retention.")
                )
            
            if not self.partner_id.type_person_id:
                raise UserError(_("The partner must have a type of person"))
        
            payment_concepts = rec._get_payment_concepts_from_invoice()

            invoice_date = rec.invoice_date_display or rec.invoice_date
            today = fields.Date.context_today(rec)
            date_accounting = max(today, invoice_date) if invoice_date else today
            vals = {
                'partner_id': rec.partner_id.id,
                'date_accounting': min(date_accounting, today),
                'type_retention': 'islr',
            }
            ctx = {
                'default_type': rec.move_type,
                'default_invoice_id': rec.id,
                'default_islr_lines': payment_concepts,
            }
            
            retention = self.env['account.retention'].with_context(ctx).create(vals)
            if not rec.company_id.create_retentions_of_suppliers_in_draft and rec.move_type in ['in_invoice']:
                retention.action_post()
            rec.islr_voucher_number = retention.number

    def _action_create_multi_islr_retention(self):
        
        line_values = []
        
        for move in self:
            line_values.append((0, 0, {
                'move_id': move.id,
            }))

        wizard = self.env['batch.retentions.wizard'].create({
            'type_retention': 'islr',
            'line_ids': line_values
        })
        
        return {
            'name': _('Generate ISLR Retention'),
            'type': 'ir.actions.act_window',
            'res_model': 'batch.retentions.wizard', 
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new'
            
        }

    
    def validate_islr(self):
        all_retention_lines = self.env['account.retention.line'].search([
            ('move_id', 'in', self.ids),
            ('retention_id.type_retention', '=', 'islr'),
            ('retention_id.state', "!=", "cancel")
        ])

        availables_retention = self.env['account.retention']

        for record in self:
            if record.state != 'posted':
                raise UserError(_(
                    "Invoice %s must be in 'Posted' state to generate a retention."
                ) % record.name)
            
            
            if not any(l.product_id.payment_concept for l in record.invoice_line_ids):
                raise UserError(_(
                    "No services with a configured 'Payment Concept' were found in the lines of invoice %s."
                ) % record.name)
            
            target = False
            if record.move_type == 'out_invoice':
                target = record.company_id.partner_id
                if not target:
                    raise UserError(_("No company partner associated with this invoice."))
                if not target.type_person_id:
                    raise UserError(_(
                        "The Company '%s' does not have an ISLR 'Type of Person' configured."
                    ) % target.name)
            else:
                target = record.partner_id
                if not target:
                    raise UserError(_("No partner/vendor associated with this invoice."))
                if not target.type_person_id:
                    raise UserError(_(
                        "The Partner/Vendor '%s' does not have an ISLR 'Type of Person' configured."
                    ) % target.name)

            retentions = all_retention_lines.filtered(lambda l: l.move_id.id == record.id)
            
            if any(l.retention_id.state == 'emitted' for l in retentions):
                raise UserError(_(
                    "Invoice %s already has a posted ISLR retention. You cannot create another one."
                ) % record.name)
            
            availables_retention |= retentions.filtered(lambda l: l.state == 'draft').mapped('retention_id')

            
                
        return availables_retention
    
    def js_remove_outstanding_partial(self, partial_id):
        self.ensure_one()

        partial = self.env["account.partial.reconcile"].browse(partial_id)
        partial_move_id = next((m for m in (partial.credit_move_id.move_id, partial.debit_move_id.move_id) if m.origin_payment_id or m.origin_payment_advanced_payment_id), None)

        payment_id = False
        if partial_move_id:
            payment_id = partial_move_id.origin_payment_id or partial_move_id.origin_payment_advanced_payment_id
      
        if payment_id and payment_id.is_retention:
            raise UserError(_(
                "You cannot unreconcile a payment that is linked to a retention. "
                "Please cancel the retention document if you want to unreconcile this payment."
            ))
        
        return super().js_remove_outstanding_partial(partial.id)
    

    def button_draft(self):
        if self.env.context.get('bypass_retention_lock'):
            return super().button_draft()
        
        for payment in self:
            
            if payment.origin_payment_id and payment.origin_payment_id.is_retention and payment.origin_payment_id.state != 'cancel':
                raise UserError(_(
                    "You cannot cancel this payment because it is a retention linked to voucher %s. "
                    "You must void or cancel the retention document first."
                ) % payment.origin_payment_id.retention_id.display_name)

        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            move._check_retention_paid_lock()

            retentions = (
                move.retention_islr_line_ids
                | move.retention_iva_line_ids
                | move.retention_municipal_line_ids
            ).mapped("retention_id").filtered(lambda r: r.state != "cancel")

            move._draft_retentions_for_resync(retentions)

        return super().button_draft()
    

    def button_cancel(self):
        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            # Cancel the invoice's non-cancelled retentions explicitly,
            # while the invoice is still posted - account.retention.write()
            # requires the invoices of a third-party retention to be
            # posted, so this must happen before super() moves the
            # invoice to 'cancel'.
            retentions = (
                move.retention_islr_line_ids
                | move.retention_iva_line_ids
                | move.retention_municipal_line_ids
            ).mapped("retention_id").filtered(lambda r: r.state != "cancel")
            if retentions:
                retentions.action_cancel()

        return super().button_cancel()

    def _draft_retentions_for_resync(self, retentions):
        """
        Validates and drafts `retentions` (this invoice's non-cancelled
        retentions) in preparation for a resync, without clearing their
        voucher number - the invoice may be reposted/recalculated right
        after and the number must still match what was already reported/
        printed (see _resync_retentions()/action_recalculate_retentions()).

        Shared by button_draft() (paso 2, which also drafts the invoice
        itself afterwards) and action_recalculate_retentions() (paso 5,
        which keeps the invoice posted) so the same validations
        (single-invoice grouping, fiscal/tax lock dates) apply to both
        entry points.
        """
        self.ensure_one()
        for retention in retentions:
            invoices = retention.retention_line_ids.mapped("move_id")
            if len(invoices) > 1:
                raise UserError(_(
                    "Invoice %(invoice)s cannot be modified: retention"
                    " %(retention)s groups several invoices (%(invoices)s)."
                    " Cancel retention %(retention)s manually first."
                ) % {
                    "invoice": self.display_name,
                    "retention": retention.display_name,
                    "invoices": ", ".join(invoices.mapped("display_name")),
                })

            # Proactively check the retention's own accounting date
            # against the fiscal/tax lock dates - same checks
            # account.move._check_fiscal_lock_dates() runs on post - so
            # the generic core error doesn't surface later with no
            # context about which retention/invoice caused it.
            lock_violations = retention.company_id._get_lock_date_violations(
                retention.date_accounting,
                fiscalyear=True,
                sale=False,
                purchase=True,
                tax=True,
                hard=True,
            )
            if lock_violations:
                raise UserError(_(
                    "Invoice %(invoice)s cannot be modified: retention"
                    " %(retention)s's accounting date (%(date)s) falls within a"
                    " locked period (%(locks)s)."
                ) % {
                    "invoice": self.display_name,
                    "retention": retention.display_name,
                    "date": retention.date_accounting,
                    "locks": retention.company_id._format_lock_dates(lock_violations),
                })

            retention.with_context(bypass_retention_lock=True).action_draft()

    def _check_retention_paid_lock(self):
        """
        Shared guard for button_draft() (paso 2) and
        action_recalculate_retentions() (paso 5): once an invoice has a
        REAL payment applied - anything other than its own retention's
        payment, which is reconciled against it as a side effect of
        emitting the retention itself, not an external payment - its
        retentions can no longer be safely desmontadas/reconstruidas.
        Evaluated before anything is desmontado, since the reconciliation
        state no longer reflects the original one afterwards. Using
        payment_state in ("paid", "in_payment") here would also block the
        common case where the retention's own payment is the only thing
        reconciled against the invoice - that case is safe to resync.
        """
        self.ensure_one()
        real_payments = self._get_reconciled_payments().filtered(
            lambda p: not p.is_retention
        )
        if real_payments:
            raise UserError(_(
                "Invoice %s cannot be modified: it has a real payment applied."
            ) % self.display_name)

    def _resync_retentions(self):
        """
        For each retention of this invoice caught mid-resync (state ==
        'draft' and payment_ids - a retention never has payment_ids in
        draft for a vendor bill unless it already went through
        action_post() once, see button_draft()/
        action_recalculate_retentions()), either cancels it (if the
        invoice no longer backs it) or rebuilds its lines/amount and
        re-emits it against the invoice's current data.
        """
        self.ensure_one()
        retentions = self._get_retentions_pending_resync().filtered(
            lambda r: r.state == "draft" and r.payment_ids
        )
        for retention in retentions:
            self._resync_retention(retention)

    def _retention_still_applies(self, retention):
        """
        Whether `retention` is still backed by a tax/concept on this
        invoice's CURRENT data - shared by _resync_retention() (which
        cancels the retention when this is False) and
        _retention_out_of_sync() (which flags it as needing attention
        either way: _resync_retention() will cancel or rebuild it).
        """
        self.ensure_one()
        if retention.type_retention == "iva":
            return any(
                self.invoice_line_ids.filtered(lambda l: l.tax_ids and l.tax_ids[0].amount > 0)
            )
        elif retention.type_retention == "islr":
            return self.is_isrl_retention_available
        else:
            return bool(
                retention.retention_line_ids.filtered(lambda l: l.move_id == self)
            )

    def _resync_retention(self, retention):
        """
        Rebuilds a single draft-by-resync retention (state == 'draft' and
        payment_ids) against this invoice's current data, or cancels it if
        the invoice no longer carries the tax/concept that justified it.
        Reused by _resync_retentions() (action_post()'s paso 3) and by
        action_recalculate_retentions() (paso 5's button), both of which
        bring the retention to this same state first.
        """
        self.ensure_one()
        retention = retention.with_context(bypass_retention_lock=True)
        payment = retention.payment_ids[:1]

        if not self._retention_still_applies(retention):
            retention.action_cancel()
            return

        if retention.type_retention in ("iva", "islr"):
            lines_of_move = retention.retention_line_ids.filtered(lambda l: l.move_id == self)
            # account.retention.line.unlink() cascades to delete the
            # linked payment, which is the SAME payment used by the other
            # lines of this invoice inside the retention - clear it first.
            lines_of_move.write({"payment_id": False})
            lines_of_move.unlink()

            if retention.type_retention == "iva":
                new_lines_data = self.env["account.retention"].compute_retention_lines_data(self, payment)
            else:
                new_lines_data = [
                    self.env["account.retention"]._prepare_islr_line_vals(
                        self, concept_id, base_amount, self.move_type, payment=payment
                    )
                    for concept_id, base_amount, _invoice_line_id in self._get_payment_concepts_from_invoice()
                ]

            retention.write({
                "retention_line_ids": [Command.create(vals) for vals in new_lines_data],
            })
        # Municipal retention lines are already kept in sync by
        # account.move.write() (onchange_economic_activity_id) whenever
        # invoice_line_ids changes - nothing to rebuild here, only the
        # amount/re-emission below.

        max_invoice_date = retention._get_max_invoice_date()
        if max_invoice_date and retention.date_accounting < max_invoice_date:
            vals = {"date_accounting": max_invoice_date}
            if retention.date and retention.date < max_invoice_date:
                vals["date"] = max_invoice_date
            retention.write(vals)

        if payment:
            payment.with_context(bypass_retention_lock=True).compute_retention_amount_from_retention_lines()

        retention.action_post()

        if retention.state != "emitted":
            raise UserError(_(
                "Could not re-emit retention %(retention)s for invoice %(invoice)s after"
                " recalculating it against its current data - open the retention for"
                " details."
            ) % {"retention": retention.display_name, "invoice": self.display_name})

    def _retention_lines_amounts_differ(self, lines_of_move, fresh_amounts, currency):
        """
        Compares this invoice's recorded retention.line amounts (for one
        retention) against freshly recomputed data, in both currencies -
        comparing against move.tax_totals['base_amount'] directly would
        give false positives with multiple IVA aliquots or several ISLR
        concepts, and would never detect anything for Municipal (whose
        base isn't derived from tax_totals at all).

        `fresh_amounts` is an iterable of (invoice_amount,
        foreign_invoice_amount) tuples, one per freshly (re)computed line.
        """
        total_invoice_amount = sum(lines_of_move.mapped("invoice_amount"))
        total_foreign_invoice_amount = sum(lines_of_move.mapped("foreign_invoice_amount"))
        fresh_invoice_amount = sum(amount for amount, _foreign in fresh_amounts)
        fresh_foreign_invoice_amount = sum(foreign for _amount, foreign in fresh_amounts)

        foreign_currency = (
            lines_of_move[:1].foreign_currency_id
            or self.company_id.foreign_currency_id
        )
        return (
            float_compare(
                total_invoice_amount, fresh_invoice_amount, precision_rounding=currency.rounding
            ) != 0
            or float_compare(
                total_foreign_invoice_amount,
                fresh_foreign_invoice_amount,
                precision_rounding=(foreign_currency.rounding if foreign_currency else currency.rounding),
            ) != 0
        )

    def _retention_out_of_sync(self, retention):
        """
        Whether an EMITTED `retention` no longer matches this invoice's
        CURRENT data: either it's no longer backed by a tax/concept (would
        be cancelled by _resync_retention()) or its declared amounts
        (lines and/or linked payment) no longer match what would be
        recalculated (would be rebuilt). Used only by
        _get_retentions_pending_resync() - _resync_retention() re-derives
        applicability itself (via _retention_still_applies()) when it
        actually acts, instead of trusting this read-only snapshot.
        """
        self.ensure_one()
        lines_of_move = retention.retention_line_ids.filtered(lambda l: l.move_id == self)
        if not lines_of_move:
            return False

        if not self._retention_still_applies(retention):
            return True

        currency = self.company_id.currency_id

        if retention.type_retention == "iva":
            try:
                fresh_lines_data = self.env["account.retention"].compute_retention_lines_data(self)
            except (UserError, AttributeError):
                # compute_retention_lines_data() would raise (even
                # AttributeError, not just UserError) on an invoice
                # without tax - treat that as out of sync instead of
                # letting it blow up the form's compute. In practice this
                # shouldn't happen here: _retention_still_applies() above
                # already catches "no tax" via "still_applies".
                return True
            fresh_amounts = [
                (d.get("invoice_amount", 0.0), d.get("foreign_invoice_amount", 0.0))
                for d in fresh_lines_data
            ]
            if self._retention_lines_amounts_differ(lines_of_move, fresh_amounts, currency):
                return True

        elif retention.type_retention == "islr":
            fresh_amounts = [
                (base_amount, base_amount)
                for _concept_id, base_amount, _invoice_line_id in self._get_payment_concepts_from_invoice()
            ]
            if self._retention_lines_amounts_differ(lines_of_move, fresh_amounts, currency):
                return True

        # Municipal lines are kept in sync automatically by write(); only
        # the linked payment amount is checked below, for all three types.

        payment = retention.payment_ids[:1]
        if payment:
            declared_total = sum(lines_of_move.mapped("retention_amount"))
            if float_compare(
                payment.amount, declared_total, precision_rounding=currency.rounding
            ) != 0:
                return True

        return False

    def _get_retentions_pending_resync(self):
        """
        Single source of truth for "this retention needs attention",
        combining the two states that used to be detected independently:
        a retention mid-resync (drafted by button_draft()/
        action_recalculate_retentions() on a previous pass, waiting to be
        rebuilt/re-emitted or cancelled - see _resync_retentions()), and
        an emitted retention that no longer matches this invoice's
        current data (drives retention_resync_pending, the warning
        banner/button, and what action_recalculate_retentions() drafts).
        """
        self.ensure_one()
        all_retentions = (
            self.retention_islr_line_ids
            | self.retention_iva_line_ids
            | self.retention_municipal_line_ids
        ).mapped("retention_id")

        mid_resync = all_retentions.filtered(lambda r: r.state == "draft" and r.payment_ids)

        out_of_sync = self.env["account.retention"]
        if self.state == "posted" and self.move_type in ("in_invoice", "in_refund"):
            emitted = all_retentions.filtered(lambda r: r.state == "emitted")
            out_of_sync = emitted.filtered(self._retention_out_of_sync)

        return mid_resync | out_of_sync

    def action_recalculate_retentions(self):
        """
        "Recalcular retenciones" button: blocked if the invoice has a real
        payment applied, then desmonta (draft, without touching the
        invoice itself) exactly the retentions pending resync, and
        rebuilds/re-emits or cancels them against the invoice's current
        data - same logic _resync_retentions() runs after a repost.
        """
        self.ensure_one()
        self._check_retention_paid_lock()

        retentions = self._get_retentions_pending_resync()
        if not retentions:
            return

        self._draft_retentions_for_resync(retentions)
        self._resync_retentions()
