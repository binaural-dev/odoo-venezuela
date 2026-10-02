from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_account_fiscalyear_closing")
class TestFiscalyearClosingConfigTemplate(TransactionCase):
    """Cubre inchange_l_map en account.fiscalyear.closing.config.template
    (models/account_fiscalyear_closing_template.py): antes de este test, la
    rama l_map=True (la que arma mapping_ids a partir del plan de cuentas)
    nunca se ejecutaba en la suite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.account_income = cls.env["account.account"].create(
            {
                "name": "Income template test",
                "code": "TPLINC",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.account_equity = cls.env["account.account"].create(
            {
                "name": "Equity template test",
                "code": "TPLEQ",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        # template_id no es required (ver account_fiscalyear_closing_template.py
        # en third-party-addons): un config.template se puede crear suelto,
        # sin colgar de un account.fiscalyear.closing.template.
        cls.config_template = cls.env["account.fiscalyear.closing.config.template"].create(
            {
                "name": "Config template test",
                "code": "TPLCFG",
                "closing_type_default": "balance",
            }
        )

    def test_inchange_l_map_populates_mapping_ids_from_account_template(self):
        self.config_template.l_map = True
        result = self.config_template.inchange_l_map()

        created_vals = [cmd[2] for cmd in result["value"]["mapping_ids"]]
        mapped_codes = [v["src_accounts"] for v in created_vals]
        self.assertIn(self.account_income.code, mapped_codes)

        vals_income = next(
            v for v in created_vals if v["src_accounts"] == self.account_income.code
        )
        # inchange_l_map resuelve la cuenta destino con
        # search(..., limit=1) sin order explicito: si el plan de cuentas
        # de la compania ya trae otra cuenta equity_unaffected (comun con
        # una plantilla contable instalada), esa puede salir primero que
        # la creada en este test. No se asume que sea account_equity: se
        # recalcula aqui con el mismo dominio que usa el metodo.
        expected_equity = self.env["account.account"].search(
            [
                ("account_type", "=", "equity_unaffected"),
                ("company_ids", "in", [self.company.id, False]),
            ],
            limit=1,
        )
        # A diferencia del modelo no-template (dest_account_id, Many2one),
        # aqui dest_account es un Char: se espera el CODIGO de la cuenta
        # destino, no su id.
        self.assertEqual(vals_income["dest_account"], expected_equity.code)
        self.assertEqual(vals_income["template_config_id"], self.config_template.id)

    def test_inchange_l_map_clears_mapping_ids_when_disabled(self):
        self.config_template.l_map = False
        result = self.config_template.inchange_l_map()
        self.assertEqual(result, {"value": {"mapping_ids": [(5, 0, 0)]}})
