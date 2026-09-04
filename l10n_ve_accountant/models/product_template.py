from collections import defaultdict

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
        # Skip entirely during chart-of-accounts loading (module install or
        # a company's fiscal localization being set up): Odoo's own
        # account.product._force_default_tax/_force_default_sale_tax
        # legitimately assigns one tax per company on shared products at
        # that point, and this is a per-record business validation aimed at
        # real user edits, not at second-guessing that system-level loading.
        # Same guard pattern already used in account_journal.py's
        # _check_payment_method_line_accounts.
        #
        # Also skip when explicitly asked to via
        # skip_single_tax_validation in context - NOT a blanket
        # config['test_enable'] check (that broke this module's own test
        # suite: 11 pre-existing TestProductTemplate tests rely on this
        # validation actually raising, and it would have silently disabled
        # the newly-added per-company logic during every test run, leaving
        # it completely unexercised). The one real, narrow use case is
        # generic accounting test fixtures shared across the whole test
        # suite (e.g. AccountTestInvoicingCommon's product_b) that
        # deliberately assign more than one tax to a single product/company
        # as generic test data, unrelated to any real Venezuelan fiscal
        # scenario - callers that need that (see
        # binaural_account_reports/tests/common.py's
        # default_env_context() override) set this key explicitly on their
        # own env instead of relying on "are we running under pytest at
        # all". The real, single-tax-per-company policy stays fully
        # enforced for actual user/business data and for this module's own
        # tests.
        if (
            self.env.context.get('chart_template_load')
            or self.env.context.get('install_mode')
            or self.env.context.get('skip_single_tax_validation')
        ):
            return {}

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
            # The "exactly one tax" policy is scoped PER COMPANY, not a flat
            # count across the whole field: a product shared between several
            # companies (no company_id of its own) legitimately carries one
            # tax per company, injected by Odoo's own native multi-company
            # mechanism (account.product._force_default_tax links each
            # company's default sale/purchase tax onto shared products).
            # Counting the union across companies as a single total would
            # reject that native, intentional setup.
            #
            # browse+read company_id under sudo(): account.tax's
            # multi-company record rule (`company_id parent_of company_ids`)
            # would otherwise raise AccessError as soon as a shared product
            # carries a tax belonging to a company outside the current
            # user's allowed companies - company_id is only ever read here
            # to group ids for this validation, nothing is mutated.
            taxes_by_company = defaultdict(lambda: self.env['account.tax'])
            for tax in self.env['account.tax'].sudo().browse(tax_ids):
                taxes_by_company[tax.company_id.id] |= tax

            # Was scoped to `if not tax_ids` before: that only caught the
            # field being entirely empty, missing the case of a shared
            # product that already carries another company's tax but none
            # for `company` - which would pass validation silently without
            # ever receiving its own default. Check per-company instead.
            company_taxes = taxes_by_company.get(company.id, self.env['account.tax'])
            if not company_taxes:
                default_tax = company[comp_field] or company.root_id.sudo()[comp_field]
                if default_tax and default_tax.id:
                    # Command.set would wipe out any other companies' taxes
                    # already present on a shared product; only safe when
                    # the field is genuinely empty. Otherwise, link (add).
                    command = (
                        fields.Command.set([default_tax.id])
                        if not tax_ids
                        else fields.Command.link(default_tax.id)
                    )
                    if is_write:
                        # FIX-060: Collect injection — do NOT mutate vals.
                        default_injections[field_name] = [command]
                    else:
                        # create() context: safe to mutate vals directly
                        # (each vals dict is private to one record).
                        vals[field_name] = [command]
                else:
                    errors.append(
                        _("- %s: No tax is assigned and the company has no "
                          "default fiscal configuration.") % label
                    )

            for tax_company_id, company_taxes_for_id in taxes_by_company.items():
                if len(company_taxes_for_id) > 1:
                    # .sudo(): a shared product can carry a tax that belongs
                    # to a company the current user doesn't have access to
                    # (multi-company record rule on res.company) - same risk
                    # already handled above for account.tax.company_id. Only
                    # the name is read here, purely to build the error
                    # message.
                    tax_company_name = (
                        self.env['res.company'].sudo().browse(tax_company_id).name
                        if tax_company_id
                        else _("no company")
                    )
                    errors.append(
                        _("- %(label)s: Has %(count)s taxes assigned for "
                          "company '%(company)s' (exactly one tax per "
                          "company is required due to local fiscal "
                          "policies).")
                        % {
                            "label": label,
                            "count": len(company_taxes_for_id),
                            "company": tax_company_name,
                        }
                    )

        if errors:
            # records may hold more than one product.template when called
            # from a batched write() (e.g. account.product's
            # _force_default_sale_tax chunked update) - records.name would
            # raise ensure_one() in that case, same class of bug already
            # handled above via mapped() for current_ids.
            name = vals.get('name') or (
                ", ".join(records.mapped('name')) if records else ''
            )
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
