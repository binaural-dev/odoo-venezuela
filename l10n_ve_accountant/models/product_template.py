from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        # Context to silence internal/automated cascade writes during creation
        ctx = dict(self.env.context, skip_tax_validation_on_write=True)
        for vals in vals_list:
            # Combo products carry no taxes of their own; taxes are derived
            # from their component products at sale time.
            if vals.get('type') != 'combo':
                self.with_context(ctx)._enforce_single_tax_vals(vals)
        return super(ProductTemplate, self.with_context(ctx)).create(vals_list)

    def write(self, vals):
        if self.env.context.get('skip_tax_validation_on_write'):
            return super(ProductTemplate, self).write(vals)

        # Enforce tax validation on any write operation to correct legacy records
        if 'taxes_id' in vals or 'supplier_taxes_id' in vals:
            # Effective type per record: the incoming vals['type'] wins for the
            # whole recordset if sent, otherwise fall back to each record's
            # current type. Combo products are exempt from the validation.
            records_to_validate = self.filtered(lambda r: vals.get('type', r.type) != 'combo')
            if records_to_validate:
                self._enforce_single_tax_vals(vals, records=records_to_validate)

        return super(ProductTemplate, self).write(vals)

    def _enforce_single_tax_vals(self, vals, records=None):
        """Validates and ensures exactly one tax is assigned by calculating 

        the net final state of the Odoo M2M commands.
        """
        errors = []
        company = self.env['res.company'].browse(vals.get('company_id')) if vals.get('company_id') else (records.company_id if records else self.env.company)

        for field_name, comp_field in [
            ('taxes_id', 'account_sale_tax_id'),
            ('supplier_taxes_id', 'account_purchase_tax_id')
        ]:
            label = self._fields[field_name].string
            # 1. Determine the baseline tax IDs of the record (if updating)
            current_ids = set(records[field_name].ids) if records else set()

            if field_name in vals and vals[field_name]:
                raw_value = vals[field_name]
                
                # Case A: Direct integer list [ID, ID]
                if isinstance(raw_value, list) and all(isinstance(x, int) for x in raw_value):
                    current_ids = set(raw_value)
                
                # Case B: Odoo M2M standard command structure
                elif isinstance(raw_value, list):
                    for cmd in raw_value:
                        if isinstance(cmd, (list, tuple)):
                            code = cmd[0]
                            if code == 6:     # Replace entire relation
                                current_ids = set(cmd[2])
                            elif code == 4:   # Link individual record
                                current_ids.add(cmd[1])
                            elif code == 3:   # Unlink individual record
                                current_ids.discard(cmd[1])
                            elif code == 5:   # Unlink all records
                                current_ids.clear()

            tax_ids = list(current_ids)

            # --- Fiscal Policy Rules Validation ---
            if not tax_ids:
                default_tax = company[comp_field] or company.root_id.sudo()[comp_field]
                if default_tax and default_tax.id:
                    vals[field_name] = [fields.Command.set([default_tax.id])]
                else:
                    errors.append(_("- %s: No tax is assigned and the company has no default fiscal configuration.") % label)
            elif len(tax_ids) > 1:
                errors.append(_("- %s: Has %s taxes assigned (exactly one tax is required due to local fiscal policies).") % (label, len(tax_ids)))

        if errors:
            name = vals.get('name') or (records.name if records else '')
            
            # Consolidated multi-error message formatting
            error_msg = (
                _("Fiscal inconsistencies were found in product: '%s':\n\n") % name
                + "\n".join(errors)
                + _("\n\nPlease correct these fields before saving your changes.")
            )
            raise UserError(error_msg)
