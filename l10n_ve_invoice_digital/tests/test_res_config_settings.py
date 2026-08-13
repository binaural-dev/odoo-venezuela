from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from unittest.mock import patch, MagicMock


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "res_config_settings")
class TestResConfigSettings(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "username_tfhka": "user",
            "password_tfhka": "pass",
            "url_tfhka": "https://api.tfhka.com",
            "token_auth_tfhka": "old_token",
            "invoice_digital_tfhka": True,
            "dispatch_guide_digital_tfhka": True,
        })
        self.settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
        })

    def test_01_onchange_invoice_digital_tfhka(self):
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
            "invoice_digital_tfhka": False,
        })
        settings._onchange_invoice_digital_tfhka()
        self.assertFalse(settings.dispatch_guide_digital_tfhka)

    @patch('requests.post')
    def test_02_action_generate_token_tfhka(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "codigo": 200,
            "mensaje": "OK",
            "token": "new_token_123",
            "expiracion": "2025-12-31T23:59:59",
        }
        mock_post.return_value = mock_resp
        self.settings.action_generate_token_tfhka()
        self.assertEqual(self.company.token_auth_tfhka, "new_token_123")

    def test_03_set_values_no_crash(self):
        # Solo verificamos que set_values existe y se puede llamar cuando dispatch_guide_digital_tfhka es False.
        self.settings.dispatch_guide_digital_tfhka = False
        self.settings.set_values()
        self.assertTrue(True)

    @patch('odoo.addons.base.models.ir_module.Module.button_immediate_install')
    def test_04_set_values_install_module(self, mock_install):
        module = self.env['ir.module.module'].sudo().search([('name', '=', 'l10n_ve_dispatch_guide_digital')], limit=1)
        if module and module.state == 'installed':
            return
        if not module:
            module = self.env['ir.module.module'].sudo().create({
                'name': 'l10n_ve_dispatch_guide_digital',
                'state': 'uninstalled',
                'category_id': self.env.ref('base.module_category_usability').id,
            })
        else:
            module.state = 'uninstalled'
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
            "dispatch_guide_digital_tfhka": True,
        })
        settings.set_values()
        mock_install.assert_called_once()

    def test_05_onchange_invoice_digital_tfhka_enabled_keeps_dispatch_guide(self):
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
            "invoice_digital_tfhka": True,
            "dispatch_guide_digital_tfhka": True,
        })
        settings._onchange_invoice_digital_tfhka()
        self.assertTrue(settings.dispatch_guide_digital_tfhka)

    @patch('odoo.addons.base.models.ir_module.Module.button_immediate_install')
    def test_06_set_values_module_already_installed_skips_install(self, mock_install):
        module = self.env['ir.module.module'].sudo().search([('name', '=', 'l10n_ve_dispatch_guide_digital')], limit=1)
        if not module:
            module = self.env['ir.module.module'].sudo().create({
                'name': 'l10n_ve_dispatch_guide_digital',
                'state': 'installed',
                'category_id': self.env.ref('base.module_category_usability').id,
            })
        else:
            module.state = 'installed'
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
            "dispatch_guide_digital_tfhka": True,
        })
        settings.set_values()
        mock_install.assert_not_called()
