from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import ValidationError
from lxml import etree
import ast

@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountant(TransactionCase):
    """Tests for invoice posting behaviour regarding the invoice date."""

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.country_ve = self.env.ref("base.ve")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
        })
        self.Journal = self.env['account.journal']
        self.Move = self.env['account.move']

        # Tipo de cambio de referencia
        self.env['res.currency.rate'].create({
            'name': fields.Date.from_string('2025-07-28'),
            'currency_id': self.currency_usd.id,
            'inverse_company_rate': 120.439,
            'company_id': self.company.id,
        })
        self.env['res.currency.rate'].create({
            'name': fields.Date.from_string('2025-07-28'),
            'currency_id': self.currency_vef.id,
            'inverse_company_rate': 1.0,
            'company_id': self.company.id,
        })

        # --- Journal bancario en USD (o se reutiliza uno existente) ---
        self.bank_journal_usd = (
            self.env['account.journal'].search(
                [("type", "=", "bank"), ("currency_id", "=", self.currency_usd.id), ("company_id", "=", self.company.id)],
                limit=1,
            )
            or self.env['account.journal'].create({
                "name": "Banco USD",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
            })
        )

        # --- Payment Method Manual inbound (reusar, no crear) ---
        self.payment_method = (
            self.env['account.payment.method'].search([('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1)
            or self.env.ref('account.account_payment_method_manual_in')
        )

        # --- Payment Method Line en el journal de BANCO (no en ventas) ---
        self.pm_line_in_usd = (
            self.env["account.payment.method.line"].search(
                [
                    ("journal_id", "=", self.bank_journal_usd.id),
                    ("payment_method_id", "=", self.payment_method.id),
                ],
                limit=1,
            )
            or self.env["account.payment.method.line"].create({
                "journal_id": self.bank_journal_usd.id,
                "payment_method_id": self.payment_method.id,
            })
        )
        acc_outstanding = self.env['account.account'].create({
            'name': 'OUTSTANDING USD',
            'code': '110000',
            'account_type': 'asset_receivable',
        })
        self.company.account_journal_payment_debit_account_id = acc_outstanding.id

        self.acc_receivable = self.env['account.account'].create({
            'name': 'CUENTAS POR COBRAR', 'code': '119800',
            'account_type': 'asset_receivable', 'reconcile': True,
        })
        self.acc_tax = self.env['account.account'].create({
            'name': 'IVA POR PAGAR', 'code': '229900',
            'account_type': 'liability_current',
        })

        # --- Impuesto ---
        self.tax_group_iva = self.env['account.tax.group'].create({
            'name': 'IVA',
            'company_id': self.company.id,
            'country_id': self.country_ve.id,
        })
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
            'country_id': self.country_ve.id,
            'tax_group_id': self.tax_group_iva.id,
            'invoice_repartition_line_ids': [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
            'refund_repartition_line_ids': [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
        })

        # --- Producto / Partner ---
        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
            'company_id': False,
        })

        self.partner_a = self.env['res.partner'].create({
            'name': 'Test Partner A',
            'customer_rank': 1,
            'company_id': False,
            'property_account_receivable_id': self.acc_receivable.id,
        })
        self.partner = self.partner_a  # usado por helpers

        # --- Journal de ventas (sin métodos de pago) ---
        self.sale_journal = (
            self.env['account.journal'].search([
                ('type', '=', 'sale'), ('company_id', '=', self.company.id)
            ], limit=1)
            or self.env['account.journal'].create({
                'name': 'Sales',
                'code': 'SAJT',  # evita colisiones con SAJ
                'type': 'sale',
                'company_id': self.company.id,
            })
        )

        self.general_journal = (
            self.env['account.journal'].search([
                ('type', '=', 'general'), ('company_id', '=', self.company.id)
            ], limit=1)
            or self.env['account.journal'].create({
                'name': 'General Acc',
                'code': 'GENACC',
                'type': 'general',
                'company_id': self.company.id,
            })
        )

        self.account_product = self.env['account.account'].create(
            {
                'name': 'VENTAS PRODUCTO',
                'code': '703000',
                'account_type': 'income',
            }
        )
        
        self.account_contado = self.env['account.account'].create(
            {
                'name': 'VENTAS AL CONTADO',
                'code': '701000',
                'account_type': 'income',
            }
        )
        self.journal_contado = self.env['account.journal'].create({
             'name': 'VENTAS CONTADO',
            'type': 'sale',
            'code': 'VCO',
            'default_account_id': self.account_contado.id
        })

        self.account_credito = self.env['account.account'].create(
            {
            'name': 'VENTAS A CREDITO',
            'code': '702000',
            'account_type': 'income',
            }
        )

        self.journal_credito = self.env['account.journal'].create({
            'name': 'VENTAS CREDITO',
            'type': 'sale',
            'code': 'VCR',
            'default_account_id': self.account_credito.id
        })

        self.Line = self.env['account.move.line']

        self.display_supports_product = 'product' in dict(self.Line._fields['display_type'].selection or [])

        # Nota: eliminamos la creación previa de self.account_payment_method_line en el journal de VENTAS
        # y también evitamos crear un payment anticipado aquí que dispare la constraint antes del test.

    def _create_invoice(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'date': fields.Date.today(),
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product.id,
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'account_id': self.account_product.id,
                })
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _create_payment(
        self,
        amount,
        *,
        currency=None,
        journal=None,
        fx_rate=None,
        fx_rate_inv=None,
        pm_line=None,
    ):
        currency = currency or self.currency_usd
        journal = journal or self.bank_journal_usd
        pm_line = pm_line or self.pm_line_in_usd

        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": amount,
            "currency_id": currency.id,
            "journal_id": journal.id,
            "payment_method_line_id": pm_line.id,
            "date": fields.Date.today(),
        }
        if fx_rate:
            vals.update({"foreign_rate": fx_rate, "foreign_inverse_rate": fx_rate_inv})

        pay = self.env["account.payment"].create(vals)
        pay.action_post()
        return pay

    def _create_draft_invoice(self, journal, line_defs):
        move = self.Move.create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'journal_id': journal.id,
            'invoice_line_ids': [(0, 0, {
                'name': ld.get('name', 'Line'),
                'product_id': ld.get('product', False) and ld['product'].id or False,
                'quantity': ld.get('qty', 1.0),
                'price_unit': ld.get('price', 100.0),
                'account_id': ld.get('account', False) and ld['account'].id or False,
                'tax_ids': [(6, 0, ld.get('taxes', []))],
                **({'display_type': ld['display_type']} if ld.get('display_type') is not None else {}),
            }) for ld in line_defs]
        })
        self.assertEqual(move.state, 'draft')
        return move

    def _assert_balances(self, move, label=""):
        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg=f"{label}: {td} != {tc}")
        return td, tc

    def test_invoice_create_and_post(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.state, 'posted')

    def test_payment_create_and_post(self):
        pay = self._create_payment(100.0)
        self.assertEqual(pay.state, 'posted')
        self.assertIsNotNone(pay.foreign_rate)
        self.assertIsNotNone(pay.foreign_inverse_rate)

    def test_monetary_field_definition(self):
        # 1. Validación de foreign_inverse_rate en account.move
        f_inv_rate_info = self.env['account.move'].fields_get(['foreign_inverse_rate'])['foreign_inverse_rate']
        self.assertEqual(f_inv_rate_info.get('digits'), 0, "El campo foreign_inverse_rate debe tener digits=0")


    # ═══════════════════════════════════════════════════════════════
    # account_move.py - tax_totals ALL keys with foreign values
    # ═══════════════════════════════════════════════════════════════

    def test_tax_totals_all_keys_foreign(self):
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 2.0, "price_unit": 500.0,
                    "discount": 10.0,
                    "account_id": self.account_product.id,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        tt = invoice.tax_totals
        for key in ['amount_untaxed', 'amount_total',
                     'formatted_amount_total', 'formatted_amount_untaxed',
                     'groups_by_subtotal', 'subtotals',
                     'formatted_discount_amount']:
            self.assertIn(key, tt, f"Missing top key: {key}")
        for key in ['foreign_amount_untaxed', 'foreign_amount_total']:
            self.assertIn(key, tt, f"Missing foreign key: {key}")
        self.assertIsInstance(tt['groups_by_subtotal'], dict)
        for gd in tt['groups_by_subtotal'].values():
            self.assertIsInstance(gd, list)
            for g in gd:
                for k in ['tax_group_name', 'tax_group_amount',
                          'tax_group_base_amount',
                          'formatted_tax_group_amount', 'formatted_tax_group_base_amount']:
                    self.assertIn(k, g, f"Missing group key: {k}")
        self.assertIsInstance(tt['subtotals'], list)
        for st in tt['subtotals']:
            for k in ['name', 'amount', 'formatted_amount']:
                self.assertIn(k, st, f"Missing subtotal key: {k}")
        self.assertAlmostEqual(tt['amount_untaxed'], 900.0, places=2)
        self.assertAlmostEqual(tt['amount_total'], 1044.0, places=2)
        self.assertGreater(tt['foreign_amount_untaxed'], 0)
        self.assertGreater(tt['foreign_amount_total'], 0)
        self.assertIn('groups_by_foreign_subtotal', tt)
        self.assertIn('foreign_subtotals', tt)
        inv_rate = invoice.foreign_inverse_rate
        self.assertAlmostEqual(tt['foreign_amount_untaxed'],
                               tt['amount_untaxed'] * inv_rate, delta=1.0)
        self.assertAlmostEqual(tt['foreign_amount_total'],
                               tt['amount_total'] * inv_rate, delta=1.0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_needed_terms with 3-line payment term
    # ═══════════════════════════════════════════════════════════════

    def test_needed_terms_multi_line_pt_foreign(self):
        payment_term = self.env['account.payment.term'].create({
            'name': '30-30-40 Test',
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 30, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 30, 'nb_days': 15}),
                Command.create({'value': 'percent', 'value_amount': 40, 'nb_days': 30}),
            ]
        })
        invoice = self.env['account.move'].with_context(
            check_move_validity=False,
        ).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'date': fields.Date.today(),
            'invoice_payment_term_id': payment_term.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product.id,
                    'quantity': 1.0,
                    'price_unit': 1000.0,
                    'account_id': self.account_product.id,
                })
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        nt = invoice.needed_terms
        self.assertEqual(len(nt), 3)
        for key, data in nt.items():
            self.assertIn('foreign_balance', data)
            self.assertGreater(abs(data['foreign_balance']), 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _check_currency_id constraint
    # ═══════════════════════════════════════════════════════════════

    def test_constraint_currency_id(self):
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.account_product.id,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                }),
            ],
        })
        with self.assertRaises(ValidationError):
            invoice.write({'currency_id': self.currency_vef.id})

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_inverse_rate_vef
    # ═══════════════════════════════════════════════════════════════

    def test_compute_inverse_rate_vef(self):
        invoice = self._create_invoice()
        self.assertIn('foreign_inverse_rate_vef', invoice._fields)
        self.assertIsNotNone(invoice.foreign_inverse_rate_vef)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _distribute_entry_real_portion
    # ═══════════════════════════════════════════════════════════════

    def test_distribute_entry_real_portion(self):
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "name": "D", "account_id": self.acc_tax.id,
                    "debit": 100.0, "credit": 0.0,
                }),
                Command.create({
                    "name": "C", "account_id": self.acc_receivable.id,
                    "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        # With amount=0 the method returns early without unbalancing the move
        move.real_portion_amount = 0.0
        move._distribute_entry_real_portion(move, move.company_currency_id)
        self.assertEqual(move.real_portion_count, 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_update_account_id
    # ═══════════════════════════════════════════════════════════════

    def test_action_update_account_id(self):
        new_categ = self.env['product.category'].create({
            'name': 'Test No Income Categ',
        })
        new_categ.property_account_income_categ_id = False
        no_inc_product = self.env['product.product'].create({
            'name': 'No Income Product', 'type': 'service', 'list_price': 100.0,
            'categ_id': new_categ.id,
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
            'supplier_taxes_id': [(5, 0, 0)],
        })
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": no_inc_product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_tax.id,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.sale_journal.default_account_id = self.account_product.id
        invoice.action_update_account_id()
        line = invoice.line_ids.filtered(lambda l: l.product_id == no_inc_product)[:1]
        if line:
            self.assertEqual(line.account_id, self.sale_journal.default_account_id)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _onchange_quantity edge case
    # ═══════════════════════════════════════════════════════════════

    def test_line_onchange_quantity_negative(self):
        invoice = self._create_invoice()
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            line.quantity = -1.0
            with self.assertRaises(ValidationError):
                line._onchange_quantity()

    def test_line_onchange_quantity_zero(self):
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'date': fields.Date.today(),
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product.id,
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'account_id': self.account_product.id,
                })
            ],
        })
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            line.quantity = 0.0
            line._onchange_quantity()
            self.assertAlmostEqual(line.quantity, 0.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - search_read override
    # ═══════════════════════════════════════════════════════════════

    def test_search_read_active_test(self):
        invoice = self._create_invoice()
        result = self.env['account.move'].search_read(
            [('id', '=', invoice.id)], ['name', 'amount_total']
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], invoice.id)
        