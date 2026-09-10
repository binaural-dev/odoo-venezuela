from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields
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

    def _create_invoice(self, seq_num=1, post=True):
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

    def _create_debit_or_credit(self, move_type, product, related_id_field, related_move):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            related_id_field: related_move.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.acc_income.id,
                "tax_ids": [Command.set([self.tax_iva16.id])],
            })],
        }
        return self.env["account.move"].create(vals)

    def _advance_correlative_sequence(self):
        # l10n_ve_invoice.action_post() valida el correlativo "espiando" el
        # number_next_actual de la secuencia "invoice.correlative" en vez de
        # consumirlo (get_sequence() solo lo hace cuando la facturacion por
        # series esta desactivada); sin este avance manual, el siguiente
        # action_post() de la prueba choca con el correlativo recien asignado.
        seq = self.env["ir.sequence"].sudo().search(
            [("code", "=", "invoice.correlative"), ("company_id", "=", self.env.company.id)], limit=1
        )
        if seq:
            seq.sudo().write({"number_next_actual": seq.number_next_actual + 1})

    def test_07_wizard_previous_debit_note_not_digitized(self):
        prod = self.env['product.product'].create({
            'name': 'Prod Debit', 'type': 'service', 'list_price': 100, 'taxes_id': [Command.set([self.tax_iva16.id])],
        })
        inv1 = self._create_invoice(post=False)
        inv1.with_context(move_action_post_alert=True).action_post()
        self._advance_correlative_sequence()
        # Se excluye de la búsqueda: solo la nota de débito queda como "no digitalizada".
        inv1.is_digitalized = True

        debit_note = self._create_debit_or_credit("out_invoice", prod, "debit_origin_id", inv1)
        debit_note.with_context(move_action_post_alert=True).action_post()
        self._advance_correlative_sequence()

        inv3 = self._create_invoice(post=False)
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': inv3.id})
        with self.assertRaises(UserError) as e:
            wizard.action_confirm()
        self.assertIn("debit note", str(e.exception).lower())

    def test_08_wizard_previous_credit_note_not_digitized(self):
        prod = self.env['product.product'].create({
            'name': 'Prod Credit', 'type': 'service', 'list_price': 100, 'taxes_id': [Command.set([self.tax_iva16.id])],
        })
        base_inv = self._create_invoice(post=False)
        base_inv.with_context(move_action_post_alert=True).action_post()
        self._advance_correlative_sequence()

        credit1 = self._create_debit_or_credit("out_refund", prod, "reversed_entry_id", base_inv)
        credit1.with_context(move_action_post_alert=True).action_post()
        self._advance_correlative_sequence()
        # credit1 queda sin digitalizar, con la menor sequence_number de los out_refund.

        credit2 = self._create_debit_or_credit("out_refund", prod, "reversed_entry_id", base_inv)
        wizard = self.env['move.action.post.alert.wizard'].create({'move_id': credit2.id})
        with self.assertRaises(UserError) as e:
            wizard.action_confirm()
        self.assertIn("credit note", str(e.exception).lower())

    def mock_api(company, endpoint_key, payload, *args, **kwargs):
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

    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request')
    def test_01b_wizard_previous_digitized(self, mock_call):
        def side_effect(company, endpoint_key, payload, *args, **kwargs):
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


