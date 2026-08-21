from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        # Context to silence internal/automated cascade writes during creation
        ctx = dict(self.env.context, skip_tax_validation_on_write=True)
        for vals in vals_list:
            self.with_context(ctx)._enforce_single_tax_vals(vals)
        return super(ProductTemplate, self.with_context(ctx)).create(vals_list)

    def write(self, vals):
        if self.env.context.get('skip_tax_validation_on_write'):
            return super(ProductTemplate, self).write(vals)

        # Enforce tax validation on any write operation to correct legacy records
        if 'taxes_id' in vals or 'supplier_taxes_id' in vals:
            self._enforce_single_tax_vals(vals, records=self)
            
        return super(ProductTemplate, self).write(vals)

    def _enforce_single_tax_vals(self, vals, records=None):
        """Validates and ensures exactly one tax is assigned by calculating 

        the net final state of the Odoo M2M commands.
        """
        errors = []
        if vals.get('company_id'):
            company = self.env['res.company'].browse(vals.get('company_id'))
        elif records and records.company_id:
            # product.template.company_id is optional (products can be
            # shared across companies) — records.company_id is a falsy
            # EMPTY recordset then, not a real company. Falling through to
            # it directly (instead of self.env.company) made every tax
            # comparison below (`t.company_id == company`) compare against
            # an empty recordset and always be False, so write() rejected
            # perfectly valid taxes as "no tax assigned".
            company = records.company_id
        else:
            company = self.env.company

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

            # Odoo's own default for these fields is computed from `self.env.companies`
            # (all allowed companies, e.g. for the admin user during module installs),
            # so the raw id list can legitimately contain one tax per allowed company.
            # The "exactly one" policy only makes sense scoped to the product's own
            # company, so ids belonging to other companies must not count towards it.
            all_taxes = self.env['account.tax'].browse(current_ids)
            own_company_taxes = all_taxes.filtered(lambda t: t.company_id == company)
            tax_ids = own_company_taxes.ids

            # --- Fiscal Policy Rules Validation ---
            if not tax_ids:
                default_tax = company[comp_field] or company.root_id.sudo()[comp_field]
                if default_tax and default_tax.id:
                    other_company_ids = (all_taxes - own_company_taxes).ids
                    vals[field_name] = [fields.Command.set(other_company_ids + [default_tax.id])]
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