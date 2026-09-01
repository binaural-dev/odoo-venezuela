from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Combo products carry no taxes of their own; taxes are derived
            # from their component products at sale time.
            if vals.get('type') != 'combo':
                self._enforce_single_tax_vals(vals)
        # FIX-062: Do NOT propagate skip_tax_validation_on_write in context —
        # let each subsequent write() decide independently based on record type.
        return super(ProductTemplate, self).create(vals_list)

    def write(self, vals):
        if self.env.context.get('skip_tax_validation_on_write'):
            return super(ProductTemplate, self).write(vals)

        # FIX-061: Trigger validation when taxes change OR when type changes
        # (e.g. combo→consu without touching taxes must still be validated).
        if 'taxes_id' in vals or 'supplier_taxes_id' in vals or 'type' in vals:
            # Effective type per record: the incoming vals['type'] wins for the
            # whole recordset if sent, otherwise fall back to each record's
            # current type. Combo products are exempt from the validation.
            records_to_validate = self.filtered(lambda r: vals.get('type', r.type) != 'combo')
            if records_to_validate:
                default_injections = self._enforce_single_tax_vals(
                    vals, records=records_to_validate,
                )
                # FIX-060: Apply defaults AFTER super().write(vals) so the
                # original vals (which may contain clear commands) don't
                # overwrite the injected defaults.
                result = super(ProductTemplate, self).write(vals)
                if default_injections:
                    records_to_validate.write(default_injections)
                return result

        return super(ProductTemplate, self).write(vals)

    def _enforce_single_tax_vals(self, vals, records=None):
        """Validates and ensures exactly one tax is assigned by calculating
        the net final state of the Odoo M2M commands.

        Behaviour differs by caller context:

        * **create()** (``records is None``): validates BOTH ``taxes_id`` and
          ``supplier_taxes_id`` and mutates ``vals`` directly to inject
          company defaults when a field is empty.  This is safe because each
          ``vals`` dict in the list is private to one record.

        * **write()** (``records`` provided): validates ONLY the tax fields
          that are actually present in ``vals`` — unless ``type`` is changing
          to a non-combo value, in which case BOTH fields are validated
          (the product may carry invalid taxes from its combo phase).
          Default injection is collected separately and applied via a
          dedicated ``records.write()`` to avoid leaking into excluded
          records (FIX-060).
        """
        errors = []
        company = (
            self.env['res.company'].browse(vals.get('company_id'))
            if vals.get('company_id')
            else ((records.company_id or self.env.company) if records else self.env.company)
        )

        # --- Determine which fields to validate ---
        is_write = records is not None
        if is_write:
            # write() context: only validate fields being changed …
            fields_to_check = [
                f for f in ('taxes_id', 'supplier_taxes_id') if f in vals
            ]
            # … unless type is changing to non-combo, then validate both
            # (the product may have carried invalid taxes as a combo).
            if 'type' in vals and vals.get('type') != 'combo':
                fields_to_check = ['taxes_id', 'supplier_taxes_id']
        else:
            # create() context: always validate both fields.
            fields_to_check = ['taxes_id', 'supplier_taxes_id']

        # Collect default injections separately (write context only).
        default_injections = {}

        for field_name, comp_field in [
            ('taxes_id', 'account_sale_tax_id'),
            ('supplier_taxes_id', 'account_purchase_tax_id'),
        ]:
            if field_name not in fields_to_check:
                continue

            label = self._fields[field_name].string

            # 1. Determine the baseline tax IDs of the record (if updating).
            # Use mapped() to safely handle multi-record recordsets
            # (Field.__get__ on multi-record raises ensure_one in Odoo 19).
            current_ids = set(records.mapped(field_name).ids) if records else set()

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
                    if is_write:
                        # FIX-060: Collect injection — do NOT mutate vals.
                        default_injections[field_name] = [
                            fields.Command.set([default_tax.id])
                        ]
                    else:
                        # create() context: safe to mutate vals directly
                        # (each vals dict is private to one record).
                        vals[field_name] = [
                            fields.Command.set([default_tax.id])
                        ]
                else:
                    errors.append(
                        _("- %s: No tax is assigned and the company has no "
                          "default fiscal configuration.") % label
                    )
            elif len(tax_ids) > 1:
                errors.append(
                    _("- %s: Has %s taxes assigned (exactly one tax is "
                      "required due to local fiscal policies).")
                    % (label, len(tax_ids))
                )

        if errors:
            name = vals.get('name') or (records.name if records else '')
            error_msg = (
                _("Fiscal inconsistencies were found in product: '%s':\n\n") % name
                + "\n".join(errors)
                + _("\n\nPlease correct these fields before saving your changes.")
            )
            raise UserError(error_msg)

        # Return default injections so the caller (write()) can apply them
        # AFTER super().write(vals), preventing the original clear commands
        # from overwriting the injected defaults (FIX-060).
        return default_injections
