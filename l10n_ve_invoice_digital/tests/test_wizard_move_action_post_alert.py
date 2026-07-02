from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import fields
from odoo.addons.account.models.account_move import AccountMove
from unittest.mock import patch


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "move_action_post_alert")
class TestMoveActionPostAlertWizard(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.user.tz = "America/Caracas"
        self.company = self.env.ref("base.main_company")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
            "invoice_digital_tfhka": True,
            "url_tfhka": "https://api.tfhka.com",
            "token_auth_tfhka": "token_fake",
            "country_id": self.env.ref('base.ve').id,
        })

        seq = self.env['ir.sequence'].create({
            'name': 'Sec Test',
            'prefix': 'INV/',
            'padding': 4,
        })
        ref_seq = self.env['ir.sequence'].create({
            'name': 'NC Test',
            'prefix': 'NC/',
            'padding': 4,
        })
        self.journal = self.env['account.journal'].create({
            'name': 'Diario Digital Test',
            'code': 'DDT',
            'type': 'sale',
            'company_id': self.company.id,
            'digital_invoice': True,
            'sequence_id': seq.id,
            'refund_sequence_id': ref_seq.id,
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Test',
            'vat': 'J12345678',
            'prefix_vat': 'J',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'test@test.com',
            'street': 'Calle Test',
        })
        self.acc_income = self.env["account.account"].create({
            "name": "Ingresos",
            "code": "4001",
            "account_type": "income",
            "company_id": self.company.id,
        })

    def _create_invoice(self, seq_num=1, post=True):
        prod = self.env['product.product'].create({
            'name': 'Prod',
            'type': 'service',
            'list_price': 100,
            'taxes_id': [(5, 0, 0)],
        })
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": prod.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.acc_income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        if post:
            inv.action_post()
        return inv

    def mock_api(endpoint_key, payload):
        if endpoint_key == "emision":
            return {"codigo": "200", "resultado": {"numeroControl": "00-00000001"}}
        elif endpoint_key == "ultimo_documento":
            return {"codigo": "200", "numeroDocumento": 1}
        elif endpoint_key == "consulta_numeraciones":
            return {
                "numeraciones": [{"serie": "NO APLICA", "hasta": "100000", "correlativo": "01"}],
                "codigo": "200",
                "mensaje": "Consulta realizada exitosamente",
            }

    def test_01_wizard_previous_not_digitized(self):
        inv1 = self._create_invoice(post=False)
        inv1.with_context(move_action_post_alert=True).action_post()
        # inv1 NO se digitaliza
        inv2 = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({
            'move_id': inv2.id,
        })
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(inv2.state, "draft")

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_01b_wizard_previous_digitized(self, mock_call):
        def side_effect(endpoint_key, payload):
            if endpoint_key == "consulta_numeraciones":
                return {
                    "numeraciones": [{"serie": "NO APLICA", "hasta": "100000", "correlativo": "01"}],
                    "codigo": "200",
                }
            elif endpoint_key == "ultimo_documento":
                return {"numeroDocumento": 1, "codigo": "200"}
            elif endpoint_key == "emision":
                return {"codigo": "200", "resultado": {"numeroControl": "00-00000001"}}
            return {}
        mock_call.side_effect = side_effect
        inv1 = self._create_invoice(post=False)
        inv1.with_context(move_action_post_alert=True).action_post()
        inv1.is_digitalized = True
        seq = self.env["ir.sequence"].sudo().search([("code", "=", "invoice.correlative"), ("company_id", "=", self.env.company.id)], limit=1)
        if seq:
            seq.number_next_actual = 9999
        inv2 = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({
            'move_id': inv2.id,
        })
        wizard.action_confirm()
        self.assertEqual(inv2.state, "posted")

    def test_02_wizard_non_digital_journal(self):
        self.journal.digital_invoice = False
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({
            'move_id': inv.id,
        })
        wizard.action_confirm()
        self.assertEqual(inv.state, "posted")

    def test_03_wizard_digitization_without_payment(self):
        self.company.digitalization_with_payment_tfhka = False
        inv = self._create_invoice(post=False)
        with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.generate_document_digital', lambda self: self.write({'is_digitalized': True})):
            wizard = self.env['move.action.post.alert.wizard'].create({
                'move_id': inv.id,
            })
            wizard.action_confirm()
            self.assertEqual(inv.state, "posted")
            self.assertTrue(inv.is_digitalized)

    def test_04_wizard_no_move_id(self):
        wizard = self.env['move.action.post.alert.wizard'].create({
            'move_id': False,
        })
        res = wizard.action_confirm()
        self.assertEqual(res.get('type'), 'ir.actions.client')

    def test_05_wizard_company_disabled(self):
        self.company.invoice_digital_tfhka = False
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({
            'move_id': inv.id,
        })
        wizard.action_confirm()
        self.assertEqual(inv.state, "posted")

    def test_06_wizard_with_payment_enabled(self):
        self.company.digitalization_with_payment_tfhka = True
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({
            'move_id': inv.id,
        })
        wizard.action_confirm()
        self.assertEqual(inv.state, "posted")


