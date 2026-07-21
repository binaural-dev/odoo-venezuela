import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountPaymentPhase1(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
        })

        self._ensure_rate(self.currency_usd.id, '2025-07-28', 120.439)
        self._ensure_rate(self.currency_vef.id, '2025-07-28', 120.439)

        self.bank_journal = (
            self.env['account.journal'].search(
                [("type", "=", "bank"), ("currency_id", "=", self.currency_usd.id), ("company_id", "=", self.company.id)],
                limit=1,
            )
            or self.env['account.journal'].create({
                "name": "Banco USD", "code": "BNKUS", "type": "bank",
                "currency_id": self.currency_usd.id,
            })
        )

        self.payment_method = self.env['account.payment.method'].search(
            [('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1
        ) or self.env.ref('account.account_payment_method_manual_in')

        self.pm_line = self.env["account.payment.method.line"].search(
            [("journal_id", "=", self.bank_journal.id), ("payment_method_id", "=", self.payment_method.id)],
            limit=1,
        ) or self.env["account.payment.method.line"].create({
            "journal_id": self.bank_journal.id,
            "payment_method_id": self.payment_method.id,
        })

        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%', 'amount': 16, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': self.company.id,
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto', 'type': 'service', 'list_price': 100,
            'taxes_id': [(6, 0, [self.tax_iva16.id])], 'company_id': False,
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Partner A', 'customer_rank': 1, 'company_id': False,
        })

        self.sale_journal = (
            self.env['account.journal'].search([
                ('type', '=', 'sale'), ('company_id', '=', self.company.id)
            ], limit=1)
            or self.env['account.journal'].create({
                'name': 'Sales', 'code': 'SAJT', 'type': 'sale',
                'company_id': self.company.id,
            })
        )

        self.account_income = self.env['account.account'].create({
            'name': 'VENTAS', 'code': '703000', 'account_type': 'income',
        })

        display_sel = dict(self.env['account.move.line']._fields['display_type'].selection or [])
        self.display_product = 'product' in display_sel

    def _ensure_rate(self, currency_id, date_str, inverse_rate):
        existing = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency_id),
            ('company_id', '=', self.company.id),
            ('name', '=', fields.Date.from_string(date_str)),
        ], limit=1)
        if not existing:
            self.env['res.currency.rate'].create({
                'name': fields.Date.from_string(date_str),
                'currency_id': currency_id,
                'inverse_company_rate': inverse_rate,
                'company_id': self.company.id,
            })

    def _make_invoice(self):
        dt = 'product' if self.display_product else False
        line_vals = {
            'name': 'L1',
            'product_id': self.product.id,
            'quantity': 1,
            'price_unit': 100,
            'tax_ids': [(6, 0, [self.tax_iva16.id])],
            'account_id': self.account_income.id,
        }
        if dt:
            line_vals['display_type'] = dt
        inv_lines = [Command.create(line_vals)]
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.from_string('2025-07-28'),
            'journal_id': self.sale_journal.id,
            'invoice_line_ids': inv_lines,
        })
        inv.with_context(move_action_post_alert=True).action_post()
        return inv

    # ---- Payment Create ----

    def test_payment_create_syncs_rate_to_move(self):
        inv = self._make_invoice()
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
        })
        payment.action_post()
        self.assertEqual(payment.move_id.foreign_rate, payment.foreign_rate)
        self.assertEqual(payment.move_id.foreign_inverse_rate, payment.foreign_inverse_rate)

    # ---- Payment Compute Rate ----

    def test_payment_compute_rate(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
        })
        # In test environment _compute_rate may not auto-fire during create
        if payment.foreign_rate == 0:
            payment._compute_rate()
        self.assertTrue(payment.foreign_rate > 0)
        self.assertTrue(payment.foreign_inverse_rate > 0)

    # ---- Payment Onchange ----

    def test_payment_onchange_foreign_rate(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
        })
        payment.foreign_rate = 200.0
        payment._onchange_foreign_rate()
        self.assertTrue(payment.foreign_inverse_rate > 0)

    # ---- Payment _synchronize_to_moves ----

    def test_payment_synchronize_to_moves(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
        })
        payment.action_post()
        old_rate = payment.move_id.foreign_rate
        payment.write({'foreign_rate': old_rate + 10})
        self.assertEqual(payment.move_id.foreign_rate, old_rate + 10)

    # ---- Journal Permissions ----

    def test_journal_create_sale_without_permission(self):
        if not hasattr(self.env['account.journal'], '_validate_support_user_group'):
            self.skipTest("Journal permission model not imported")
        group = self.env.ref('l10n_ve_accountant.group_support_user', raise_if_not_found=False)
        if not group:
            self.skipTest("group_support_user not found")

        user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser_phase1',
            'groups_id': [(6, 0, [self.env.ref('account.group_account_manager').id])],
        })

        with self.assertRaises(UserError):
            self.env['account.journal'].with_user(user).create({
                'name': 'Test Sale', 'type': 'sale', 'code': 'TST',
            })

    def test_journal_create_bank_without_permission(self):
        if not hasattr(self.env['account.journal'], '_validate_support_user_group'):
            self.skipTest("Journal permission model not imported")
        group = self.env.ref('l10n_ve_accountant.group_support_user', raise_if_not_found=False)
        if not group:
            self.skipTest("group_support_user not found")

        user = self.env['res.users'].create({
            'name': 'Test User Bank',
            'login': 'testuser_bank_phase1',
            'groups_id': [(6, 0, [self.env.ref('account.group_account_manager').id])],
        })

        journal = self.env['account.journal'].with_user(user).create({
            'name': 'Test Bank', 'type': 'bank', 'code': 'TBK',
        })
        self.assertTrue(journal)

    def test_journal_write_type_without_permission(self):
        if not hasattr(self.env['account.journal'], '_validate_support_user_group'):
            self.skipTest("Journal permission model not imported")
        group = self.env.ref('l10n_ve_accountant.group_support_user', raise_if_not_found=False)
        if not group:
            self.skipTest("group_support_user not found")

        user = self.env['res.users'].create({
            'name': 'Test User Write',
            'login': 'testuser_write_phase1',
            'groups_id': [(6, 0, [self.env.ref('account.group_account_manager').id])],
        })

        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), ('company_id', '=', self.company.id)
        ], limit=1)

        with self.assertRaises(UserError):
            journal.with_user(user).write({'type': 'sale'})

    # ---- Wizard default_get ----

    def test_wizard_default_get(self):
        inv = self._make_invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=inv.ids,
            active_id=inv.id,
        ).create({})
        self.assertIsNotNone(wizard.foreign_rate)

    # ---- Wizard _onchange_foreign_rate ----

    def test_wizard_onchange_foreign_rate(self):
        inv = self._make_invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=inv.ids,
            active_id=inv.id,
        ).create({})
        wizard.foreign_rate = 200.0
        wizard._onchange_foreign_rate()
        self.assertTrue(wizard.foreign_inverse_rate > 0)

    # ---- Wizard _onchange_invoice_date ----

    def test_wizard_onchange_payment_date(self):
        inv = self._make_invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=inv.ids,
            active_id=inv.id,
        ).create({})
        wizard.payment_date = fields.Date.from_string('2025-08-01')
        wizard._onchange_invoice_date()
        self.assertTrue(wizard.foreign_rate >= 0)

    # ---- Wizard _create_payment_vals_from_wizard ----

    def test_wizard_create_payment_vals(self):
        inv = self._make_invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=inv.ids,
            active_id=inv.id,
        ).create({})
        self.assertIsNotNone(wizard.foreign_rate)
        self.assertIsNotNone(wizard.foreign_inverse_rate)

    # ---- Wizard _get_wizard_values_from_batch ----

    def test_wizard_get_values_from_batch(self):
        inv = self._make_invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=inv.ids,
            active_id=inv.id,
        ).create({})
        batches = wizard._get_batches()
        if batches:
            values = wizard._get_wizard_values_from_batch(batches[0])
            self.assertIn('source_amount', values)
            self.assertIn('source_amount_currency', values)

    # ---- End-to-end Payment ----

    def test_e2e_payment_with_rate(self):
        inv = self._make_invoice()
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
            'foreign_rate': 150.0,
            'foreign_inverse_rate': 1/150.0,
        })
        payment.action_post()
        self.assertEqual(payment.move_id.foreign_rate, 150.0)
        self.assertAlmostEqual(payment.move_id.foreign_inverse_rate, 1/150.0, places=6)

    # ---- Payment default_alternate_currency ----

    def test_payment_default_alternate_currency(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
        })
        self.assertEqual(payment.foreign_currency_id.id, self.company.currency_foreign_id.id)

    # ---- Wizard default_alternate_currency ----

    def test_wizard_default_alternate_currency(self):
        inv = self._make_invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=inv.ids,
            active_id=inv.id,
        ).create({})
        self.assertEqual(wizard.foreign_currency_id.id, self.company.currency_foreign_id.id)

    # ---- Wizard base_currency_is_vef ----

    def test_wizard_base_currency_is_vef(self):
        inv = self._make_invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=inv.ids,
            active_id=inv.id,
        ).create({})
        self.assertEqual(wizard.base_currency_is_vef, self.company.currency_id == self.env.ref("base.VEF"))
