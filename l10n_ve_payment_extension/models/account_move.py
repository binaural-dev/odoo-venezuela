from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
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
        retention_vals = {
            "date_accounting": self.date,
            "date": self.date if self.move_type in ["in_invoice", "out_invoice"] else False,
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
                        
            if record.move_type == 'in_invoice':
                xml_action_id = 'l10n_ve_payment_extension.action_retention_islr_supplier'
            elif record.move_type == 'out_invoice':
                xml_action_id = 'l10n_ve_payment_extension.action_retention_islr_client'
            else:
                raise UserError(_("This action is only valid for customer or vendor invoices."))


            action = self.env.ref(xml_action_id).read()[0]
            ctx = safe_eval(action.get('context', '{}'))
            ctx.update({
                'default_partner_id': record.partner_id.id,
                'default_invoice_id': record.id,
                'default_date_accounting': fields.Date.today(),
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
                        base_amount = abs(line.price_unit) if use_price_unit else abs(line.move_id.tax_totals["base_amount"])
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

            vals = {
                'partner_id': rec.partner_id.id,
                'date_accounting': fields.Date.today(),
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
                
        return super().button_draft()
    

    