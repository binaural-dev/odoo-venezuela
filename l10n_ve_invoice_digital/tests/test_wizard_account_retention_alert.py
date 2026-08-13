from odoo.tests import TransactionCase, tagged
from unittest.mock import patch


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "retention_alert_wizard")
class TestAccountRetentionAlertWizard(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.user.tz = "America/Caracas"
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "invoice_digital_tfhka": True,
            "url_tfhka": "https://api.tfhka.com",
            "token_auth_tfhka": "token_fake",
        })

    def _mock_api(endpoint_key, payload):
        if endpoint_key == "emision":
            return {"codigo": "200", "resultado": {"numeroControl": "00-00000001"}}
        elif endpoint_key == "ultimo_documento":
            return {"codigo": "200", "numeroDocumento": 1}
        elif endpoint_key == "consulta_numeraciones":
            return {
                "numeraciones": [
                    {"serie": "NO APLICA", "hasta": "100000", "correlativo": "01"},
                ],
                "codigo": "200",
                "mensaje": "Consulta realizada exitosamente",
            }

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api', side_effect=_mock_api)
    def test_01_wizard_action_confirm(self, mock_call):
        partner = self.env["res.partner"].create({
            "name": "Test",
            "vat": "J12345678",
            "prefix_vat": "J",
            "country_id": self.env.ref("base.ve").id,
            "phone": "04141234567",
            "email": "test@test.com",
            "street": "Calle",
        })
        retention = self.env["account.retention"].create({
            "partner_id": partner.id,
            "type": "in_invoice",
            "type_retention": "iva",
            "state": "emitted",
        })
        wizard = self.env["account.retention.alert.wizard"].create({
            "move_id": retention.id,
        })
        wizard.action_confirm()
        self.assertTrue(retention.is_digitalized)

    def test_02_wizard_action_cancel(self):
        retention = self.env["account.retention"].create({
            "partner_id": self.env["res.partner"].create({"name": "Test"}).id,
            "type": "in_invoice",
            "type_retention": "iva",
            "state": "emitted",
        })
        wizard = self.env["account.retention.alert.wizard"].create({
            "move_id": retention.id,
        })
        result = wizard.action_cancel()
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")
