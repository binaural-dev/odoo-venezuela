
from odoo import _, api, models, fields
from odoo.fields import Domain
from collections import defaultdict
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class BatchRetentionsWizard(models.TransientModel):
    _name = "batch.retentions.wizard"

    name = fields.Char(string='Name', compute='_compute_name', store=True)

    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        required=True,
        string="Retention Type"
    )

    line_ids = fields.One2many('batch.retentions.wizard.lines', 'wizard_id', string="Invoices to Process",store=True)

    valid_line_ids = fields.One2many('batch.retentions.wizard.lines', 'wizard_id', compute="_compute_split_lines", string="Valid Invoices",readonly=False)
    invalid_line_ids = fields.One2many('batch.retentions.wizard.lines', 'wizard_id', compute="_compute_split_lines", string="Invalid Invoices",readonly=False)

    group_retentions = fields.Boolean('Grouped Retentions by partner', default=False, help="Generate retentions grouped Invoices by partner")

    has_payed_invoices = fields.Boolean('Has payed invoices',compute="_compute_values")

    has_draft_cancel_invoices = fields.Boolean('hast draft and cancel invoices',compute="_compute_values")

    has_not_allow_retentions_islr_invoices = fields.Boolean('has not allow retentions islr invoices',compute="_compute_values")

    @api.depends('line_ids','line_ids.move_id')
    def _compute_split_lines(self):
        for record in self:
            valid_lines = record.line_ids.filtered(
                lambda l: l.is_isrl_retention_available 
                and not l.has_emited_islr_retention 
                and l.count_islr_retention == 0 
                and l.state == 'posted'
            )
            
            invalid_lines = record.line_ids - valid_lines
            
            record.valid_line_ids = valid_lines
            record.invalid_line_ids = invalid_lines
            record.invalid_line_ids.post_retention = False

    @api.depends('line_ids', 'line_ids.move_id', 'line_ids.state', 'line_ids.payment_state', 'line_ids.is_isrl_retention_available')
    def _compute_values(self):
        for record in self:
            has_payed = False
            has_invalid_state = False
            has_not_allowed = False

            for line in record.line_ids:
                if line.payment_state in ['paid']:
                    has_payed = True
                
                if line.state in ['draft', 'cancel']:
                    has_invalid_state = True
                
                if not line.is_isrl_retention_available:
                    has_not_allowed = True

            record.has_payed_invoices = has_payed
            record.has_draft_cancel_invoices = has_invalid_state
            record.has_not_allow_retentions_islr_invoices = has_not_allowed


    @api.depends('type_retention')
    def _compute_name(self):
        for record in self:
            if record.type_retention:
                selection_label = dict(self._fields['type_retention'].selection).get(record.type_retention)
                record.name = f"Retention: {selection_label}"
            else:
                record.name = "/"

    def create_muti_retencion(self):
        self.ensure_one()
        lines_to_process = self.valid_line_ids
        
        if not lines_to_process:
            raise UserError(_("There are not valid retentions to Process"))

        retencion_ids = []
        if not self.group_retentions:
            for rec in lines_to_process:
                payment_concepts = rec.move_id._get_payment_concepts_from_invoice()

                if not payment_concepts:
                    continue

                vals = {
                    'partner_id': rec.move_id.partner_id.id,
                    'date_accounting': fields.Date.today(),
                    'type_retention': 'islr',
                }
                
                ctx = {
                    'default_type': rec.move_id.move_type,
                    'default_invoice_id': rec.move_id.id,
                    'default_islr_lines': payment_concepts,
                }
                
                retention = self.env['account.retention'].with_context(ctx).create(vals)
                if not self.env.company.create_retentions_of_suppliers_in_draft and rec.move_id.move_type in ['in_invoice','in_refund','in_debit'] and rec.post_retention:
                    retention.action_post()
                
                rec.move_id.islr_voucher_number = retention.number
                retencion_ids.append(retention.id)
        else:
        
            partner_data = {}
            for line in lines_to_process:
                p_id = line.partner_id.id
                if p_id not in partner_data:
                    partner_data[p_id] = {'lines': self.env['batch.retentions.wizard.lines'], 'moves': self.env['account.move']}
                partner_data[p_id]['lines'] |= line
                partner_data[p_id]['moves'] |= line.move_id
            
            for partner_id, data in partner_data.items():
                multi_islr_lines = []
                for move in data['moves']:
                    concepts = move._get_payment_concepts_from_invoice()
                    if concepts:
                        multi_islr_lines.extend(concepts)
                
                if not multi_islr_lines:
                    continue
            

                ref_move = data['moves'][0]
                ctx = {
                    'default_type': ref_move.move_type,
                    'default_islr_lines': multi_islr_lines,
                    'multi':True
                }
                
                retention = self.env['account.retention'].with_context(ctx).create({
                    'partner_id': partner_id,
                    'date_accounting': fields.Date.today(),
                    'type_retention': 'islr',
                })
                
                if any(data['lines'].mapped('post_retention')):
                    if not self.env.company.create_retentions_of_suppliers_in_draft and ref_move.move_type in ['in_invoice', 'in_refund', 'in_debit'] and ref_move.post_retention:
                        retention.action_post()
                
                data['moves'].write({'islr_voucher_number': retention.number})
                retencion_ids.append(retention.id)

        return {
                'name': _('ISLR Retention'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.retention',
                'view_mode': 'list,form',
                'domain': [('id', 'in', retencion_ids)],
                'target': 'current',
            }