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
                if code == fields.Command.SET:      # Replace entire relation
                    current_ids = set(cmd[2])
                elif code == fields.Command.LINK:   # Link individual record
                    current_ids.add(cmd[1])
                elif code == fields.Command.UNLINK:  # Unlink individual record
                    current_ids.discard(cmd[1])
                elif code == fields.Command.CLEAR:  # Unlink all records
                    current_ids.clear()
    return current_ids


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
                # TI-15065: each injection is scoped to only the records that
                # actually need it (not a single write() call for the whole
                # records_to_validate), so products that already had a valid
                # tax are never touched. Each of these write() calls passes
                # skip_tax_validation_on_write=True, so it does NOT re-enter
                # validation — no recursion to reason about.
                for injection in default_injections.values():
                    injection['records'].with_context(
                        skip_tax_validation_on_write=True
                    ).write({injection['field']: injection['value']})
                return result

        return super(ProductTemplate, self).write(vals)

    def _relevant_tax_ids(self, tax_ids, company, tax_company_map=None):
        """TI-15065: account.tax.company_id is mandatory and NOT
        company_dependent, and taxes_id/supplier_taxes_id on
        product.template carry no company domain either — so a product
        shared across companies/branches (no company_id, common for base
        products) can legitimately accumulate taxes from OTHER companies
        without that being a fiscal violation FOR THIS company (e.g. when
        creating a new company/branch, account._force_default_sale_tax
        links the new company's default tax onto every product, including
        shared ones that already carry a different company's own valid
        tax). Only taxes this company can actually use — its own, or
        inherited from an ancestor in the branch hierarchy
        (``company.parent_ids``) — count towards the "exactly one tax"
        rule; a tax belonging to an unrelated company is irrelevant to
        this validation.

        ``tax_company_map`` (optional ``{tax_id: company_id}``) lets a
        batch caller (``_enforce_single_tax_vals_write``) resolve every
        tax's company with a single query up front, instead of one
        ``browse().exists()`` per record and per field."""
        if not tax_ids:
            return []
        relevant_company_ids = set(company.sudo().parent_ids.ids)
        if tax_company_map is None:
            taxes = self.env['account.tax'].sudo().browse(tax_ids).exists()
            tax_company_map = {t.id: t.company_id.id for t in taxes}
        return [
            tax_id for tax_id in tax_ids
            if tax_company_map.get(tax_id) in relevant_company_ids
        ]

    def _enforce_single_tax_vals(self, vals, records=None):
        """Validates and ensures exactly one tax is assigned by calculating
        the net final state of the Odoo M2M commands.

        Behaviour differs by caller context:

        * **create()** (``records is None``): validates BOTH ``taxes_id`` and
          ``supplier_taxes_id`` and mutates ``vals`` directly to inject
          company defaults when a field is empty.  This is safe because each
          ``vals`` dict in the list is private to one record.

        * **write()** (``records`` provided, one or more): validates ONLY
          the tax fields that are actually present in ``vals`` — unless
          ``type`` is changing to a non-combo value, in which case BOTH
          fields are validated (the product may carry invalid taxes from
          its combo phase). Deliberate consequence: a write() that only
          touches ``taxes_id`` no longer "repairs" an empty
          ``supplier_taxes_id`` on the same record — narrower than the
          original "correct legacy records on any write" behaviour, traded
          for not raising on fields the caller never intended to touch.

          TI-15065: validates EACH record in ``records`` INDIVIDUALLY,
          against that record's own current taxes merged with the vals
          commands — not the union of every record's taxes (as
          ``records.mapped(field_name)`` computed). A single write() can
          legitimately touch many unrelated products at once (e.g.
          account.chart.template forcing a default tax on every product of
          a company via a `Command.link`); each product may already have
          its own, independently valid, single tax, and ``records.company_id``
          / ``records.name`` are scalar accesses that raise ``ensure_one()``
          on Odoo 19 once ``records`` has 2+ ids. Default injection is
          collected per record and applied via dedicated ``write()`` calls
          scoped to just the records that need it, to avoid overwriting
          records that already have a valid tax.
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
                    # Concatenate on top of whatever commands the caller
                    # already sent (e.g. taxes from other companies it
                    # wants to keep) instead of overwriting them.
                    vals[field_name] = list(vals.get(field_name) or []) + [
                        fields.Command.link(default_tax.id)
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
            name = vals.get('name') or ''
            self._raise_fiscal_inconsistency([(name, errors)])

    def _enforce_single_tax_vals_write(self, vals, records):
        fields_to_check = [
            f for f in ('taxes_id', 'supplier_taxes_id') if f in vals
        ]
        if 'type' in vals and vals.get('type') != 'combo':
            fields_to_check = ['taxes_id', 'supplier_taxes_id']

        default_injections = {}
        errors_by_record = []

        # TI-15065 follow-up: resolve every tax's company with a single
        # query for the whole batch, instead of one browse().exists() per
        # record and per field — this method only runs on product
        # create/write (not a hot path), but a chart-template load can
        # touch thousands of products in one call.
        all_tax_ids = set()
        for record in records:
            for field_name in fields_to_check:
                all_tax_ids.update(
                    _apply_m2m_commands(record[field_name].ids, vals.get(field_name))
                )
        tax_company_map = {
            t.id: t.company_id.id
            for t in self.env['account.tax'].sudo().browse(all_tax_ids).exists()
        } if all_tax_ids else {}

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
                    tax_company_map=tax_company_map,
                )

                if not tax_ids:
                    default_tax = company[comp_field] or company.root_id.sudo()[comp_field]
                    if default_tax and default_tax.id:
                        # FIX-060: Collect injection — do NOT mutate vals.
                        # Keyed by (field, tax) rather than just field: two
                        # records in the same batch can belong to different
                        # companies and thus need different default taxes
                        # for the same field — a plain field_name key would
                        # make the second record's injection silently reuse
                        # the first record's tax.
                        entry = default_injections.setdefault((field_name, default_tax.id), {
                            'field': field_name,
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

        # Returned to write(), which applies each injection AFTER
        # super().write(vals) (FIX-060).
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
