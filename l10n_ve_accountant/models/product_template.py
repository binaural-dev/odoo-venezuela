from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _apply_m2m_commands(current_ids, raw_value):
    """Applies an Odoo M2M `write()` value (list of (6,0,ids)/(4,id)/(3,id)/
    (5,0,0) commands, or a plain list of ids) on top of a baseline set of
    ids, returning the resulting set. Pure function so it can be reused for
    both a single record's baseline (write) and an empty baseline
    (create)."""
    current_ids = set(current_ids)
    if not raw_value:
        return current_ids

    # Case A: Direct integer list [ID, ID]
    if isinstance(raw_value, list) and all(isinstance(x, int) for x in raw_value):
        return set(raw_value)

    # Case B: Odoo M2M standard command structure
    if isinstance(raw_value, list):
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
    return current_ids


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
            default_injections = self._enforce_single_tax_vals(vals, records=self)
            result = super(ProductTemplate, self).write(vals)
            # TI-15065: apply per-record default-tax injections AFTER
            # super().write(vals), each scoped to only the records that
            # actually need it, so products that already had a valid tax
            # are never touched.
            for field_name, injection in default_injections.items():
                injection['records'].with_context(
                    skip_tax_validation_on_write=True
                ).write({field_name: injection['value']})
            return result

        return super(ProductTemplate, self).write(vals)

    def _relevant_tax_ids(self, tax_ids, company):
        """TI-15065: account.tax.company_id is mandatory and NOT
        company_dependent, and taxes_id/supplier_taxes_id on
        product.template carry no company domain either — so a product
        shared across companies/branches (common for base/demo products,
        and expected in a branch setup like this one) can legitimately
        accumulate taxes from OTHER companies without that being a fiscal
        violation FOR THIS company. Only taxes this company can actually
        use — its own, or inherited from an ancestor in the branch
        hierarchy (``company.parent_ids``) — count towards the "exactly
        one tax" rule; a tax belonging to an unrelated company is simply
        irrelevant to this validation."""
        if not tax_ids:
            return []
        relevant_company_ids = set(company.sudo().parent_ids.ids)
        taxes = self.env['account.tax'].sudo().browse(tax_ids).exists()
        return taxes.filtered(lambda t: t.company_id.id in relevant_company_ids).ids

    def _enforce_single_tax_vals(self, vals, records=None):
        """Validates and ensures exactly one tax is assigned by calculating
        the net final state of the Odoo M2M commands.

        Behaviour differs by caller context:

        * **create()** (``records is None``): validates BOTH ``taxes_id``
          and ``supplier_taxes_id`` and mutates ``vals`` directly to inject
          company defaults when a field is empty. Safe because each
          ``vals`` dict in the list is private to one record.

        * **write()** (``records`` provided, one or more): validates ONLY
          the tax fields actually present in ``vals``, and — TI-15065 —
          validates EACH record in ``records`` INDIVIDUALLY, against that
          record's own current taxes merged with the vals commands. A
          single write() can legitimately touch many unrelated products at
          once (e.g. account.chart.template forcing a default tax on every
          product of a company via a `Command.link`); each product may
          already have its own, independently valid, single tax. Computing
          one combined/aggregated tax set across the whole recordset (as a
          previous version of this method did) conflates different
          products' taxes and raises false positives — and worse, blocks
          company creation entirely, since the account module's default
          chart-template loading always writes across every product at
          once. Default injection is collected separately per record and
          applied via dedicated ``write()`` calls scoped to just the
          records that need it, to avoid overwriting records that already
          have a valid tax.
        """
        if records is None:
            return self._enforce_single_tax_vals_create(vals)
        return self._enforce_single_tax_vals_write(vals, records)

    def _enforce_single_tax_vals_create(self, vals):
        company = (
            self.env['res.company'].browse(vals.get('company_id'))
            if vals.get('company_id') else self.env.company
        )
        errors = []
        for field_name, comp_field in [
            ('taxes_id', 'account_sale_tax_id'),
            ('supplier_taxes_id', 'account_purchase_tax_id'),
        ]:
            label = self._fields[field_name].string
            tax_ids = self._relevant_tax_ids(
                _apply_m2m_commands(set(), vals.get(field_name)), company
            )

            if not tax_ids:
                default_tax = company[comp_field] or company.root_id.sudo()[comp_field]
                if default_tax and default_tax.id:
                    vals[field_name] = [fields.Command.link(default_tax.id)]
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
            name = vals.get('name') or ''
            self._raise_fiscal_inconsistency([(name, errors)])

    def _enforce_single_tax_vals_write(self, vals, records):
        fields_to_check = [
            f for f in ('taxes_id', 'supplier_taxes_id') if f in vals
        ]
        default_injections = {}
        errors_by_record = []

        for record in records:
            company = (
                self.env['res.company'].browse(vals.get('company_id'))
                if vals.get('company_id')
                else (record.company_id or self.env.company)
            )
            record_errors = []
            for field_name, comp_field in [
                ('taxes_id', 'account_sale_tax_id'),
                ('supplier_taxes_id', 'account_purchase_tax_id'),
            ]:
                if field_name not in fields_to_check:
                    continue

                label = self._fields[field_name].string
                tax_ids = self._relevant_tax_ids(
                    _apply_m2m_commands(record[field_name].ids, vals.get(field_name)),
                    company,
                )

                if not tax_ids:
                    default_tax = company[comp_field] or company.root_id.sudo()[comp_field]
                    if default_tax and default_tax.id:
                        entry = default_injections.setdefault(field_name, {
                            'records': records.browse(),
                            'value': [fields.Command.link(default_tax.id)],
                        })
                        entry['records'] |= record
                    else:
                        record_errors.append(
                            _("- %s: No tax is assigned and the company has no "
                              "default fiscal configuration.") % label
                        )
                elif len(tax_ids) > 1:
                    record_errors.append(
                        _("- %s: Has %s taxes assigned (exactly one tax is "
                          "required due to local fiscal policies).")
                        % (label, len(tax_ids))
                    )

            if record_errors:
                errors_by_record.append((record.name, record_errors))

        if errors_by_record:
            self._raise_fiscal_inconsistency(errors_by_record)

        return default_injections

    def _raise_fiscal_inconsistency(self, errors_by_record):
        """Raises a UserError describing the fiscal errors found. When more
        than one product is affected (TI-15065), each product's errors are
        grouped under its own name; a single affected product keeps the
        original flat format."""
        names = ', '.join(name for name, _errs in errors_by_record)
        if len(errors_by_record) > 1:
            lines = []
            for name, errs in errors_by_record:
                lines.append(_("Product '%s':") % name)
                lines.extend(errs)
        else:
            lines = errors_by_record[0][1]

        error_msg = (
            _("Fiscal inconsistencies were found in product: '%s':\n\n") % names
            + "\n".join(lines)
            + _("\n\nPlease correct these fields before saving your changes.")
        )
        raise UserError(error_msg)
