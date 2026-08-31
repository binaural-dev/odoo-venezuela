from odoo import api, models, fields, _
from markupsafe import Markup
from odoo.exceptions import UserError

class TaxUnit(models.Model):
    _inherit = "tax.unit"

    available_date = fields.Date(string="Publish Date", store=True, tracking=True, required=True, default=fields.Date.today)

    @api.constrains('value', 'available_date')
    def _check_national_value_consistency(self):
        # La UT es nacional: un mismo available_date debe tener el mismo
        # value en todas las compañías. fees.retention es global (no tiene
        # company_id) y toma la UT de la fecha vigente sin filtrar por
        # compañía, así que un valor divergente entre compañías corrompería
        # las retenciones de todas.
        for record in self:
            if not record.available_date:
                continue

            mismatched = self.sudo().search([
                ('id', '!=', record.id),
                ('available_date', '=', record.available_date),
                ('value', '!=', record.value),
            ], limit=1)
            if mismatched:
                raise UserError(_(
                    "The tax unit value must be the same for every company on a given "
                    "date. Company '%s' already has a different value (%s) for %s."
                ) % (mismatched.company_id.name, mismatched.value, record.available_date))

    @api.constrains('value', 'available_date')
    def _check_unique_tax_unit(self):
        for record in self:
            if not record.available_date:
                continue
            
            domain_date = [
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id),
                ('available_date', '=', record.available_date),
            ]
            if self.search_count(domain_date) > 0:
                raise UserError(_("There cannot be two tax units with the same date (%s).")
                                % record.available_date)

            domain_both = [
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id),
                ('value', '=', record.value),
                ('available_date', '=', record.available_date),
            ]
            if self.search_count(domain_both) > 0:
                raise UserError(_("Already exists a record with the value  %s for the date %s.") 
                                % (record.value, record.available_date))

    @api.model_create_multi
    def create(self, vals_list):
        records = super(TaxUnit, self).create(vals_list)
        for record in records:
            record._update_active_status()
        return records

    def write(self, vals):
        # 'install_mode' está activo durante la instalación/actualización de
        # CUALQUIER módulo, no solo de este, así que usarlo como bypass aquí
        # desactivaría esta protección en situaciones ajenas a este módulo.
        # 'bypass_tax_unit_lock' es una clave propia que solo nuestro código
        # puede activar deliberadamente (p.ej. para corregir el registro
        # semilla, aunque hoy eso se hace con _write y no pasa por aquí).
        for record in self:
            if not self.env.context.get('bypass_tax_unit_lock'):
                if not record.status and any(field not in {'status'} for field in vals):
                    raise UserError(_("You cannot edit a tax unit that is not active."))

        res = super(TaxUnit, self).write(vals)

        if 'value' in vals:
            for record in self:
                if not record.status:
                    continue

                retentions = self.env['fees.retention'].search([])

                for ret in retentions:
                    ret.tax_unit_ids = record.id

                    if hasattr(ret, '_compute_amount_subtract'):
                        ret._compute_amount_subtract()

                    
                    message = Markup(_(
                        "<strong>Update Tax Unit:</strong> %s<br/>"
                        "<strong>Tariff:</strong> %s<br/>"
                        "<strong>Value of the unit:</strong> %s<br/>"
                        "<strong>New subtracted value:</strong> %s"
                    )) % (
                        record.name, 
                        ret.name or '', 
                        record.value, 
                        f"{ret.amount_subtract:,.2f}"
                    )
                    self.message_post(body=message)

                    message = Markup(_(
                        "<strong>Update Tariff:</strong> %s<br/>"
                        "<strong>Tariff:</strong> %s<br/>"
                        "<strong>Value of the unit:</strong> %s<br/>"
                        "<strong>New subtracted value:</strong> %s"
                    )) % (
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
        """ Lógica para que, por compañía, solo el registro con fecha mayor sea True """
        companies = self.mapped('company_id') or self.env.company
        for company in companies:
            latest_record = self.search(
                [('company_id', '=', company.id)], order='available_date desc, id desc', limit=1
            )
            if not latest_record:
                continue

            all_records = self.search([('company_id', '=', company.id)])
            for rec in all_records:
                new_status = (rec.id == latest_record.id)
                if rec.status != new_status:
                    super(TaxUnit, rec).write({'status': new_status})

            self._trigger_retention_update(latest_record)


    def _trigger_retention_update(self, tax_unit_record):
        retentions = self.env['fees.retention'].search([])
        retentions.write({'tax_unit_ids': tax_unit_record.id})
        
        for ret in retentions:

            if hasattr(ret, '_compute_amount_subtract'):
                ret._compute_amount_subtract()
            message = Markup(_(
                "<strong>Updating by new Active Tax Unit</strong><br/>"
                "<strong>Unit:</strong> %s<br/>"
                "<strong>New Value:</strong> %s<br/>"
                "<strong>New Subtraction:</strong> %s"
            )) % (
                tax_unit_record.name,
                tax_unit_record.value,
                f"{ret.amount_subtract:,.2f}"
            )
            ret.message_post(body=message)