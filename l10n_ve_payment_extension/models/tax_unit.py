from odoo import api, models, fields, _
from markupsafe import Markup
from odoo.exceptions import UserError

class TaxUnit(models.Model):
    _inherit = "tax.unit"

    name = fields.Char(string="Description", help="Tax Unit Description", required=True, store=True)
    value = fields.Float(help="Tax unit value", required=True, store=True, tracking=True)
    status = fields.Boolean(default=True, string="Active?", store=True, tracking=True)

    available_date = fields.Date(string="Publish Date", store=True, tracking=True, required=True)

    @api.constrains('value', 'available_date')
    def _check_unique_tax_unit(self):
        for record in self:
            if not record.available_date:
                continue
            
            domain_date = [
                ('id', '!=', record.id),
                ('available_date', '=', record.available_date),
            ]
            if self.search_count(domain_date) > 0:
                raise UserError(_("There cannot be two tax units with the same date (%s).") 
                                % record.available_date)

            domain_both = [
                ('id', '!=', record.id),
                ('value', '=', record.value),
                ('available_date', '=', record.available_date),
            ]
            if self.search_count(domain_both) > 0:
                raise UserError(_("Already exists a record with the value  %s for the date %s.") 
                                % (record.value, record.available_date))

    @api.model
    def create(self, vals):
        record = super(TaxUnit, self).create(vals)
        record._update_active_status()
        return record

    def write(self, vals):
        for record in self:
            if not record.status and any(field not in {'status'} for field in vals):
                raise UserError(_("You cannot edit a tax unit that is not active."))

        res = super(TaxUnit, self).write(vals)

        if 'value' in vals:
            for record in self:
                if not record.status:
                    continue

                retentions = self.env['fees.retention'].search([
                    ('apply_subtracting', '=', True),
                    ('status', '=', True),
                ])

                for ret in retentions:
                    ret.tax_unit_ids = record.id 

                    if hasattr(ret, '_compute_amount_subtract'):
                        ret._compute_amount_subtract()

                    
                    message = Markup(
                        "<strong>Actualización de Unidad Tributaria:</strong> %s<br/>"
                        "<strong>Tarifa:</strong> %s<br/>"
                        "<strong>Valor de la unidad:</strong> %s<br/>"
                        "<strong>Nuevo sustraendo calculado:</strong> %s"
                    ) % (
                        record.name, 
                        ret.name or '', 
                        record.value, 
                        f"{ret.amount_subtract:,.2f}"
                    )
                    self.message_post(body=message)

                    message = Markup(
                        "<strong>Actualización Tarifa:</strong> %s<br/>"
                        "<strong>Tarifa:</strong> %s<br/>"
                        "<strong>Valor de la unidad:</strong> %s<br/>"
                        "<strong>Nuevo sustraendo calculado:</strong> %s"
                    ) % (
                        record.name, 
                        ret.name or '', 
                        record.value, 
                        f"{ret.amount_subtract:,.2f}"
                    )

                    ret.message_post(body=message)

        if 'available_date' in vals or 'status' in vals:
            self._update_active_status()

        return res

    def _update_active_status(self):
        """ Lógica para que solo el registro con fecha mayor sea True """
        latest_record = self.search([], order='available_date desc, id desc', limit=1)
        if latest_record:
            all_records = self.search([])
            for rec in all_records:
                new_status = (rec.id == latest_record.id)
                if rec.status != new_status:
                    super(TaxUnit, rec).write({'status': new_status})
                
                    self._trigger_retention_update(rec)
                else:
                    self._trigger_retention_update(rec)


    def _trigger_retention_update(self, tax_unit_record):
        retentions = self.env['fees.retention'].search([
            ('apply_subtracting', '=', True),
            ('status', '=', True)
        ])
        retentions.write({'tax_unit_ids': tax_unit_record.id})
        for ret in retentions:

            if hasattr(ret, '_compute_amount_subtract'):
                ret._compute_amount_subtract()
            message = Markup(
                "<strong>Actualización por Nueva Unidad Activa</strong><br/>"
                "<strong>Unidad:</strong> %s<br/>"
                "<strong>Nuevo Valor:</strong> %s<br/>"
                "<strong>Nuevo Sustraendo:</strong> %s"
            ) % (
                tax_unit_record.name,
                tax_unit_record.value,
                f"{ret.amount_subtract:,.2f}"
            )
            ret.message_post(body=message)
