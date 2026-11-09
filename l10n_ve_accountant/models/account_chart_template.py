import logging

from odoo import models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

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

    # TODO(20.0): revisar si el core ya repara xmlids de la raíz al cargar una sucursal; de ser así, eliminar este override.
    def _pre_load_data(self, template_code, company, template_data, data):
        """Re-vincula los xmlids de cuentas de la compañía raíz antes de cargar una sucursal.

        Reutiliza del core `company_xmlid`, `ir.model.data._update_xmlids` y el
        patrón de búsqueda por código de `_pre_reload_data`. Se sobrescribe un
        método privado porque es el único punto que corre antes de
        `_post_load_data`, donde `ref()` resuelve los xmlids de cuentas de la
        raíz y falla si se perdieron. El contrato queda fijado en
        tests/test_chart_template_relink.py (riesgo en upgrades 17->18->19).
        """
        if company.parent_id:
            self._l10n_ve_relink_root_xmlids(template_code, company, template_data, data)
        return super()._pre_load_data(template_code, company, template_data, data)

    def _l10n_ve_relink_root_xmlids(self, template_code, company, template_data, data):
        """Restaura los xmlids faltantes o huérfanos de las cuentas que una
        sucursal resuelve con `ref()` (que cae a `parent_ids[0]`).
        Nunca crea cuentas."""
        root = company.parent_ids[0]
        if not root.chart_template or root.chart_template != template_code:
            return
        Account = self.env['account.account']
        xmlids = set()
        # property_* del template que apuntan a cuentas (ver _post_load_data)
        for field, model in self._get_property_accounts(template_data.get('additional_properties', {})).items():
            value = template_data.get(field)
            model_field = self.env[model]._fields.get(field)
            if (
                value and isinstance(value, str) and '.' not in value
                and model_field and model_field.comodel_name == 'account.account'
            ):
                xmlids.add(value)
        # valores de res.company que apuntan a cuentas
        company_fields = self.env['res.company']._fields
        for field, value in data.get('res.company', {}).get(company.id, {}).items():
            model_field = company_fields.get(field)
            if (
                isinstance(value, str) and value and '.' not in value
                and model_field and model_field.comodel_name == 'account.account'
            ):
                xmlids.add(value)
        if not xmlids:
            return

        # Chequeo barato: el xmlid existe Y apunta a una cuenta existente.
        names = {f"{root.id}_{xmlid}": xmlid for xmlid in xmlids}
        self.env.cr.execute(SQL(
            """
            SELECT imd.name
              FROM ir_model_data imd
              JOIN account_account aa ON aa.id = imd.res_id
             WHERE imd.module = 'account'
               AND imd.model = 'account.account'
               AND imd.name IN %s
            """,
            tuple(names),
        ))
        found = {row[0] for row in self.env.cr.fetchall()}
        missing = [xmlid for name, xmlid in names.items() if name not in found]
        if not missing:
            return

        chart_accounts = self._get_chart_template_model_data(template_code, 'account.account')
        code_digits = int(template_data.get('code_digits', 6))
        repaired = 0
        for xmlid in sorted(missing):
            code = chart_accounts.get(xmlid, {}).get('code')
            if not code:
                continue  # no es una cuenta del plan (p. ej. una propiedad de diario)
            normalized_code = f'{code:<0{code_digits}}'
            root_accounts = Account.sudo().with_company(root).with_context(active_test=False)
            query = root_accounts._search(Account._check_company_domain(root))
            account_code = root_accounts._field_to_sql('account_account', 'code', query)
            query.add_where(SQL("%s SIMILAR TO %s", account_code, f'{code}0*'))
            accounts = Account.sudo().browse(query)
            exact = accounts.filtered(lambda a: a.with_company(root).code == normalized_code)
            account = exact[:1] or (accounts if len(accounts) == 1 else Account)
            if not account:
                _logger.warning(
                    "Cannot re-link xmlid %s of root company %s: %s account(s) found with code %s.",
                    xmlid, root.display_name, len(accounts), code,
                )
                continue
            if not account.active:
                _logger.warning(
                    "Re-linking xmlid %s of root company %s to archived account %s: "
                    "the branch default will point to an archived account.",
                    xmlid, root.display_name, account.display_name,
                )
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': self.company_xmlid(xmlid, root),
                'record': account,
                'noupdate': True,
            }])
            repaired += 1
        if repaired:
            _logger.info(
                "Re-linked %s account xmlid(s) of root company %s before loading branch %s.",
                repaired, root.display_name, company.display_name,
            )
