from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_pos.models.pos_config import L10N_VE_LIMIT_LOAD_PARTNER

PARAM = "point_of_sale.limited_customer_count"


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosPartnerLoadLimit(TransactionCase):
    """TA-85635: the PoS loads at least L10N_VE_LIMIT_LOAD_PARTNER customers by default,
    without lowering an instance that already has a higher limit."""

    def _run_with(self, value):
        param_model = self.env["ir.config_parameter"].sudo()
        param_model.set_param(PARAM, value)
        self.env["pos.config"]._l10n_ve_set_default_pos_partner_load_limit()
        return param_model.get_param(PARAM)

    def test_module_data_raises_odoo_default(self):
        # After installing the module, the parameter is no longer Odoo's 100.
        value = self.env["ir.config_parameter"].sudo().get_param(PARAM)
        self.assertGreaterEqual(int(value), L10N_VE_LIMIT_LOAD_PARTNER)

    def test_raises_odoo_default(self):
        self.assertEqual(self._run_with(100), str(L10N_VE_LIMIT_LOAD_PARTNER))

    def test_sets_missing_parameter(self):
        # set_param(False) deletes the parameter.
        self.assertEqual(self._run_with(False), str(L10N_VE_LIMIT_LOAD_PARTNER))

    def test_replaces_non_numeric_value(self):
        self.assertEqual(self._run_with("abc"), str(L10N_VE_LIMIT_LOAD_PARTNER))

    def test_keeps_higher_value(self):
        self.assertEqual(self._run_with(8000), "8000")

    def test_keeps_value_equal_to_limit(self):
        self.assertEqual(
            self._run_with(L10N_VE_LIMIT_LOAD_PARTNER), str(L10N_VE_LIMIT_LOAD_PARTNER)
        )

    def test_pos_uses_raised_limit(self):
        self._run_with(100)
        config = self.env["pos.config"].create({"name": "Caja límite clientes"})
        self.assertEqual(config._get_limited_partner_count(), L10N_VE_LIMIT_LOAD_PARTNER)
