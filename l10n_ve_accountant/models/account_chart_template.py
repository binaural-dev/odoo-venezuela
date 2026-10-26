import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _post_load_data(self, template_code, company, template_data):
        """Let a branch inherit the account defaults of its root company.

        When a branch is created, the core resolves the property accounts of the
        template (e.g. receivable/payable) through the xmlid of the root company
        (``account.<root_id>_<xmlid>``). A root whose chart was not loaded from
        the template (custom or migrated chart) has no such xmlid and the branch
        creation fails. For the branches only, when that xmlid is missing the
        branch takes the default the root company already has.
        """
        company = company or self.env.company
        if not company.parent_id:
            return super()._post_load_data(template_code, company, template_data)

        data = dict(template_data)
        unresolved = []
        for field, model in self._get_property_accounts(data.get('additional_properties', {})).items():
            if model == 'res.company':
                # Fields of the company itself (e.g. the down payment account), not defaults of
                # another model: they are not in ir.default and are left to the core.
                continue
            xmlid = data.get(field)
            if xmlid and field in self.env[model]._fields and not self.ref(xmlid, raise_if_not_found=False):
                unresolved.append((field, model, xmlid))
                data.pop(field)
        res = super()._post_load_data(template_code, company, data)

        root = company.root_id
        for field, model, xmlid in unresolved:
            default = self.env['ir.default']._get(model, field, company_id=root.id)
            if not default and self.env['ir.default']._get(model, field):
                # A default for all the companies: the branch already gets it, nothing to copy.
                _logger.info(
                    "Branch %s: the xmlid '%s' of the chart template %s does not exist, "
                    "using the default for all the companies of %s.%s.",
                    company.display_name, xmlid, template_code, model, field,
                )
                continue
            if not default:
                raise UserError(_(
                    "The branch %(branch)s cannot be created: the chart template xmlid '%(xmlid)s' does not exist "
                    "and its parent company %(root)s has no default value for %(model)s.%(field)s.",
                    branch=company.display_name, xmlid=xmlid, root=root.display_name, model=model, field=field,
                ))
            _logger.warning(
                "Branch %s: the xmlid '%s' of the chart template %s does not exist, using the default of %s for %s.%s.",
                company.display_name, xmlid, template_code, root.display_name, model, field,
            )
            self.env['ir.default'].set(model, field, default, company_id=company.id)
        return res

    def _load(self, template_code, company, install_demo, force_create=True):
        res = super()._load(template_code, company, install_demo, force_create=force_create)
        # The constraint on `l10n_ve_use_foreign_exchange_diff` is skipped
        # while the chart loads (its config is written in separate steps),
        # so validate it once the load finishes: a chart that did not set
        # the exchange journal/accounts cannot keep the (default) flag on.
        company = company.sudo()
        if company.l10n_ve_use_foreign_exchange_diff:
            missing = company._l10n_ve_foreign_exchange_diff_missing_config()
            if missing:
                _logger.warning(
                    "Chart template %s left company %s without %s: disabling "
                    "'Use Alternate Currency Exchange Difference'.",
                    template_code, company.display_name, ", ".join(missing),
                )
                company.with_context(l10n_ve_skip_exchange_diff_check=True).l10n_ve_use_foreign_exchange_diff = False
        return res
