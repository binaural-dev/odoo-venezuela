from odoo.tests import TransactionCase, tagged
from odoo import Command, fields
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
            "foreign_currency_id": self.currency_vef.id,
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
        # O19: l10n_ve_invoice.action_post exige impuesto en cada linea de
        # producto, asi que el fixture necesita uno. El nombre del GRUPO es el
        # que TFHKA mapea, y en el plan venezolano real es "IVA 16%".
        self.tax_group = self.env['account.tax.group'].create({'name': 'IVA 16%'})
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': self.tax_group.id,
        })
        self.acc_income = self.env["account.account"].create({
            "name": "Ingresos",
            "code": "4001",
            "account_type": "income",
            # O19: account.account es multi-compañía (company_ids M2m).
            "company_ids": [Command.link(self.company.id)],
        })

    def _create_invoice(self, post=True):
        prod = self.env['product.product'].create({
            'name': 'Prod',
            'type': 'service',
            'list_price': 100,
            'taxes_id': [Command.set([self.tax_iva16.id])],
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
                "tax_ids": [Command.set([self.tax_iva16.id])],
            })],
        })
        if post:
            inv.action_post()
        return inv

    # ------------------------------------------------------------------
    # Confirming enqueues instead of digitalizing synchronously
    # ------------------------------------------------------------------

    def test_wizard_confirm_enqueues_eligible_invoice(self):
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': inv.id})

        wizard.action_confirm()

        self.assertEqual(inv.state, "posted")
        self.assertFalse(inv.is_digitalized)
        self.assertEqual(inv.tfhka_digitalization_state, "queued")
        self.assertTrue(inv.tfhka_queued_at)

    def test_wizard_confirm_then_cron_digitalizes(self):
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': inv.id})
        wizard.action_confirm()

        with patch(
            'odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.generate_document_digital',
            lambda self: self.write({'is_digitalized': True}),
        ):
            self.env['account.move']._tfhka_cron_process_queue()

        self.assertTrue(inv.is_digitalized)
        self.assertEqual(inv.tfhka_digitalization_state, "success")

    def test_wizard_non_digital_journal_does_not_enqueue(self):
        self.journal.digital_invoice = False
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': inv.id})

        wizard.action_confirm()

        self.assertEqual(inv.state, "posted")
        self.assertEqual(inv.tfhka_digitalization_state, "none")

    def test_wizard_no_move_id(self):
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': False})
        res = wizard.action_confirm()
        self.assertEqual(res.get('type'), 'ir.actions.client')

    def test_wizard_company_disabled_does_not_enqueue(self):
        self.company.invoice_digital_tfhka = False
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': inv.id})

        wizard.action_confirm()

        self.assertEqual(inv.state, "posted")
        self.assertEqual(inv.tfhka_digitalization_state, "none")

    def test_wizard_with_payment_enabled_does_not_enqueue(self):
        self.company.digitalization_with_payment_tfhka = True
        inv = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': inv.id})

        wizard.action_confirm()

        self.assertEqual(inv.state, "posted")
        self.assertEqual(inv.tfhka_digitalization_state, "none")
