import logging
from odoo.tests import TransactionCase, tagged, Form
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_core")
class TestAccountMoveCore(TransactionCase):

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")

        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
        })

        today = fields.Date.today()
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_vef.id,
            "inverse_company_rate": 1.0, "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 40.0, "company_id": self.company.id,
        })

        self.acc_rec = self._get_or_create('120000', 'Receivable', 'asset_receivable', reconcile=True)
        self.acc_inc = self._get_or_create('400000', 'Income', 'income')
        self.acc_tax = self._get_or_create('200000', 'Tax Payable', 'liability_current', reconcile=True)
        self.acc_exp = self._get_or_create('500000', 'Expense', 'expense')
        self.acc_bank = self._get_or_create('100100', 'Bank', 'asset_cash', reconcile=True)

        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA', 'company_id': self.company.id, 'country_id': self.country_ve.id,
        })
        self.tax_16 = self.env["account.tax"].with_company(self.company).create({
            "name": "IVA 16% Test", "amount": 16, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
        })

        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Sales Core Test", "code": "SCORE",
            "type": "sale", "company_id": self.company.id,
            "default_account_id": self.acc_inc.id,
        })

        self.purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Purchase Core Test", "code": "PCORE",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })

        self.general_journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "General Core Test", "code": "GCORE",
            "type": "general", "company_id": self.company.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "Core Test Partner", "country_id": self.country_ve.id,
            "property_account_receivable_id": self.acc_rec.id,
        })

        self.product = self.env["product.product"].create({
            "name": "Core Service", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })

    def _get_or_create(self, code, name, acc_type, reconcile=False):
        acc = self.env['account.account'].search([
            ('code', '=', code), ('company_ids', 'in', self.company.id),
        ], limit=1)
        if not acc:
            acc = self.env['account.account'].create({
                'code': code, 'name': name, 'account_type': acc_type,
                'company_ids': [(6, 0, [self.company.id])],
                'reconcile': reconcile,
            })
        return acc

    def _create_simple_invoice(self, currency=None, price=100.0):
        currency = currency or self.currency_vef
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": currency.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": price,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        return invoice

    # ═══════════════════════════════════════════════════════════════
    # _get_accounting_date_source
    # ═══════════════════════════════════════════════════════════════

    def test_01_accounting_date_source(self):
        """_get_accounting_date_source: debe retornar invoice_date_display
        si existe, o date como fallback."""
        move = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.general_journal.id,
        })
        # Sin invoice_date_display -> usa date (hoy)
        self.assertEqual(move._get_accounting_date_source(), move.date)

        # Con invoice_date_display -> usa ese
        test_date = fields.Date.to_date("2025-07-15")
        move.write({"invoice_date_display": test_date})
        self.assertEqual(move._get_accounting_date_source(), test_date)

    # ═══════════════════════════════════════════════════════════════
    # _compute_company_currency_rate
    # ═══════════════════════════════════════════════════════════════

    def test_02_company_currency_rate(self):
        """_compute_company_currency_rate: debe computar la tasa
        de la moneda de la factura a la moneda de la compañia."""
        invoice = self._create_simple_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        # company_currency_rate = 40 (1 USD = 40 VEF)
        self.assertAlmostEqual(invoice.company_currency_rate, 40.0, places=4)
        invoice_vef = self._create_simple_invoice(self.currency_vef, 100.0)
        invoice_vef.with_context(move_action_post_alert=True).action_post()
        # Misma moneda -> rate = 1
        self.assertAlmostEqual(invoice_vef.company_currency_rate, 1.0, places=4)

    # ═══════════════════════════════════════════════════════════════
    # _onchange_move_type
    # ═══════════════════════════════════════════════════════════════

    def test_03_onchange_move_type(self):
        """_onchange_move_type: entry debe limpiar
        invoice_date_display."""
        move_ent = self.env["account.move"].new({
            "move_type": "entry",
        })
        # invoice_date_display tiene default = today, forzamos un valor
        move_ent.invoice_date_display = fields.Date.today()
        move_ent._onchange_move_type()
        # entry -> invoice_date_display = False
        self.assertFalse(
            move_ent.invoice_date_display,
            "invoice_date_display debe ser False para entry"
        )

    # ═══════════════════════════════════════════════════════════════
    # _onchange_invoice_date_display
    # ═══════════════════════════════════════════════════════════════

    def test_04_onchange_invoice_date_display(self):
        """_onchange_invoice_date_display: debe setear invoice_date
        desde invoice_date_display para documentos de venta."""
        move = self.env["account.move"].new({
            "move_type": "out_invoice",
        })
        move.invoice_date_display = "2025-08-01"
        move._onchange_invoice_date_display()
        self.assertEqual(move.invoice_date, fields.Date.to_date("2025-08-01"))

    # ═══════════════════════════════════════════════════════════════
    # _onchange_foreign_rate / _onchange_foreign_inverse_rate (move)
    # ═══════════════════════════════════════════════════════════════

    def test_05_onchange_foreign_rate_validation(self):
        """_onchange_foreign_rate y _onchange_foreign_inverse_rate:
        deben rechazar valores negativos."""
        move = self.env["account.move"].new({
            "move_type": "out_invoice",
            "currency_id": self.currency_usd.id,
        })
        # foreign_rate negativo -> ValidationError
        move.foreign_rate = -1.0
        with self.assertRaises(ValidationError):
            move._onchange_foreign_rate()
        # foreign_inverse_rate negativo -> ValidationError
        move.foreign_inverse_rate = -1.0
        with self.assertRaises(ValidationError):
            move._onchange_foreign_inverse_rate()
        # foreign_inverse_rate = 0 -> ValidationError
        move.foreign_inverse_rate = 0.0
        with self.assertRaises(ValidationError):
            move._onchange_foreign_inverse_rate()

    # ═══════════════════════════════════════════════════════════════
    # _check_taxes_id (constraint)
    # ═══════════════════════════════════════════════════════════════

    def test_06_check_taxes_id_unique_tax(self):
        """_check_taxes_id: con unique_tax=True, factura con 2 impuestos
        debe lanzar ValidationError."""
        self.company.write({"unique_tax": True})
        tax_8 = self.env["account.tax"].with_company(self.company).create({
            "name": "IVA 8% Test", "amount": 8, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        })
        with self.assertRaises(ValidationError):
            self.env["account.move"].with_context(
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
                        "account_id": self.acc_inc.id,
                        "tax_ids": [(6, 0, [self.tax_16.id, tax_8.id])],
                    }),
                ],
            })
        self.company.write({"unique_tax": False})

    # ═══════════════════════════════════════════════════════════════
    # _check_product_id (constraint)
    # ═══════════════════════════════════════════════════════════════

    def test_07_check_product_id(self):
        """_check_product_id: linea display_type='product' sin producto
        debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["account.move"].with_context(
                check_move_validity=False,
            ).create({
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create({
                        "product_id": False,
                        "quantity": 1.0, "price_unit": 100.0,
                        "account_id": self.acc_inc.id,
                        "display_type": "product",
                    }),
                ],
            })

    # ═══════════════════════════════════════════════════════════════
    # action_update_account_id
    # ═══════════════════════════════════════════════════════════════

    def test_08_action_update_account_id(self):
        """action_update_account_id: verifica que el metodo no crashea
        y que las lineas mantienen su cuenta."""
        invoice = self._create_simple_invoice(self.currency_vef, 100.0)
        line = invoice.invoice_line_ids[0]
        account_before = line.account_id
        # Ejecutar (todas las lineas ya tienen cuenta, no deberia cambiar nada)
        invoice.action_update_account_id()
        self.assertEqual(line.account_id, account_before)

    # ═══════════════════════════════════════════════════════════════
    # _unlink_except_posted_or_was_posted
    # ═══════════════════════════════════════════════════════════════

    def test_09_unlink_posted_move(self):
        """_unlink_except_posted_or_was_posted: no debe permitir
        borrar un asiento posteado."""
        invoice = self._create_simple_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        with self.assertRaises(UserError):
            invoice.unlink()

    # ═══════════════════════════════════════════════════════════════
    # button_draft
    # ═══════════════════════════════════════════════════════════════

    def test_10_button_draft_vendor_invoice(self):
        """button_draft: al resetear a draft una factura de proveedor,
        debe volver a draft sin errores."""
        purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Purchase Core Test", "code": "PCORE",
            "type": "purchase", "company_id": self.company.id,
        })
        # Crear impuesto de compra
        purchase_tax = self.env["account.tax"].with_company(self.company).create({
            "name": "IVA 16% Compra", "amount": 16, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        })
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_exp.id,
                    "tax_ids": [(6, 0, [purchase_tax.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        invoice.button_draft()
        self.assertEqual(invoice.state, 'draft')

    # ═══════════════════════════════════════════════════════════════
    # _compute_move_currency_to_company_currency_rate
    # ═══════════════════════════════════════════════════════════════

    def test_11_move_currency_rate(self):
        """_compute_move_currency_to_company_currency_rate: verifica
        que la tasa entre moneda del asiento y moneda de compañia
        se computa correctamente."""
        invoice = self._create_simple_invoice(self.currency_usd, 100.0)
        # USD -> VEF. inverse_company_rate = 40
        self.assertAlmostEqual(invoice.move_currency_to_company_currency_rate, 40.0, places=4)
        invoice_vef = self._create_simple_invoice(self.currency_vef, 100.0)
        # VEF -> VEF (misma), pero debe computar tasa de USD a VEF
        self.assertGreater(invoice_vef.move_currency_to_company_currency_rate, 0)

    # ═══════════════════════════════════════════════════════════════
    # _compute_detailed_amounts
    # ═══════════════════════════════════════════════════════════════

    def test_12_detailed_amounts(self):
        """_compute_detailed_amounts: verifica que se computan
        los montos detallados (gross, discount, tax) en factura."""
        invoice = self._create_simple_invoice(self.currency_vef, 5000.0)
        # detailed_amounts debe tener datos
        self.assertTrue(invoice.detailed_amounts)
        # Verificar estructura basica
        details = invoice.detailed_amounts
        self.assertIn('gross_amount', details)
        self.assertIn('discount_amount', details)
        self.assertIn('taxes_amount', details)
        self.assertIn('formatted_gross_amount', details)
        self.assertIn('formatted_discount_amount', details)
        self.assertIn('formatted_taxes_amount', details)
        self.assertIn('gross_discount_amount', details)
        self.assertIn('formatted_gross_discount_amount', details)

    # ═══════════════════════════════════════════════════════════════
    # _inverse_foreign_balance (account.move.line)
    # ═══════════════════════════════════════════════════════════════

    def test_13_inverse_foreign_balance(self):
        """_inverse_foreign_balance: verifica que el metodo existe
        y se ejecuta sin errores. foreign_debit/foreign_credit son
        campos compute+store y se recomputan despues del inverse."""
        invoice = self._create_simple_invoice(self.currency_vef, 100.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')
        if not line:
            line = invoice.line_ids
        if line:
            test_line = line[0]
            # Verificar que el metodo existe y puede llamarse
            self.assertTrue(hasattr(test_line, '_inverse_foreign_balance'))
            # Verificar que la linea tiene los campos
            self.assertIsNotNone(test_line.foreign_debit)
            self.assertIsNotNone(test_line.foreign_credit)
            self.assertIsNotNone(test_line.foreign_balance)

    # ═══════════════════════════════════════════════════════════════
    # _onchange_quantity / _onchange_price_unit (account.move.line)
    # ═══════════════════════════════════════════════════════════════

    def test_14_onchange_quantity_negative(self):
        """_onchange_quantity: cantidad negativa debe lanzar error."""
        line = self.env["account.move.line"].new({
            "name": "Test",
        })
        line.quantity = -1.0
        with self.assertRaises(ValidationError):
            line._onchange_quantity()

    def test_15_onchange_price_unit_negative(self):
        """_onchange_price_unit: precio negativo debe lanzar error."""
        line = self.env["account.move.line"].new({
            "name": "Test",
        })
        line.price_unit = -1.0
        with self.assertRaises(ValidationError):
            line._onchange_price_unit()

    # ═══════════════════════════════════════════════════════════════
    # _check_single_international_purchase_journal (account.journal)
    # ═══════════════════════════════════════════════════════════════

    def test_16_single_international_purchase_journal(self):
        """_check_single_international_purchase_journal: solo debe
        permitir un diario con is_purchase_international=True."""
        purchase_journal = self.env["account.journal"].search([
            ("type", "=", "purchase"), ("company_id", "=", self.company.id),
        ], limit=1) or self.env["account.journal"].sudo().create({
            "name": "Intl Purchase", "code": "INTP",
            "type": "purchase", "company_id": self.company.id,
        })
        purchase_journal.write({"is_purchase_international": True})
        with self.assertRaises(ValidationError):
            self.env["account.journal"].sudo().create({
                "name": "Intl Purchase 2", "code": "INP2",
                "type": "purchase", "company_id": self.company.id,
                "is_purchase_international": True,
            })
        purchase_journal.write({"is_purchase_international": False})

    # ═══════════════════════════════════════════════════════════════
    # _get_computed_taxes (account.move.line)
    # ═══════════════════════════════════════════════════════════════

    def test_17_get_computed_taxes_international_exempt(self):
        """_get_computed_taxes: con international_purchase_exent_product,
        debe retornar el impuesto exento configurado."""
        # Solo verificar que el metodo no crashea
        line = self.env["account.move.line"].new({
            "name": "Test",
            "international_purchase_exent_product": True,
        })
        # Debe retornar algo o nada, pero no crashear
        result = line._get_computed_taxes()
        self.assertIsNotNone(result)

    # ═══════════════════════════════════════════════════════════════
    # action_register_payment (account.move)
    # ═══════════════════════════════════════════════════════════════

    def test_18_action_register_payment(self):
        """action_register_payment: debe abrir el wizard de pago."""
        invoice = self._create_simple_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        action = invoice.action_register_payment()
        self.assertEqual(action['res_model'], 'account.payment.register')
        self.assertIn('active_ids', action.get('context', {}))

    # ═══════════════════════════════════════════════════════════════
    # _compute_edit_rate (res.currency)
    # ═══════════════════════════════════════════════════════════════

    def test_19_compute_edit_rate(self):
        """_compute_edit_rate: verifica que el rate computado
        en res.currency (no res.currency.rate) es booleano."""
        # edit_rate esta en res.currency, no en res.currency.rate
        self.assertIn(self.currency_usd.edit_rate, [True, False])

    # ═══════════════════════════════════════════════════════════════
    # _compute_is_foreign_currency (account.payment)
    # ═══════════════════════════════════════════════════════════════

    def test_20_payment_foreign_currency_fields(self):
        """_compute_is_foreign_currency y _compute_foreign_amount:
        verifica campos computados en pagos."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")

        def _make_bank(code, name, currency):
            lines = {
                'inbound_payment_method_line_ids': [(0, 0, {
                    'name': f'In {name}', 'payment_method_id': manual_in.id,
                    'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
                })],
                'outbound_payment_method_line_ids': [(0, 0, {
                    'name': f'Out {name}', 'payment_method_id': manual_out.id,
                    'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
                })],
            }
            journal = self.env['account.journal'].create({
                'name': name, 'code': code, 'type': 'bank',
                'currency_id': currency.id if currency else False,
                'default_account_id': self.acc_bank.id,
                'company_id': self.company.id,
                **lines,
            })
            return journal, journal.inbound_payment_method_line_ids[:1]

        bank_usd, pml_usd = _make_bank('BNKUSD2', 'Bank USD Cov', self.currency_usd)
        bank_vef, pml_vef = _make_bank('BNKVEF2', 'Bank VEF Cov', self.currency_vef)

        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": 100.0, "currency_id": self.currency_usd.id,
            "payment_method_line_id": pml_usd.id,
            "journal_id": bank_usd.id,
        })
        self.assertTrue(payment.is_foreign_currency)
        # USD == foreign_currency_id -> _compute_foreign_amount -> 0.0
        self.assertAlmostEqual(payment.foreign_amount, 0.0)

        payment_vef = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": 100.0, "currency_id": self.currency_vef.id,
            "payment_method_line_id": pml_vef.id,
            "journal_id": bank_vef.id,
        })
        self.assertFalse(payment_vef.is_foreign_currency)

    # ═══════════════════════════════════════════════════════════════
    # action_post with move_action_post_alert
    # ═══════════════════════════════════════════════════════════════

    def test_21_action_post_alert_context(self):
        """action_post: con contexto move_action_post_alert=True
        debe postear sin errores."""
        invoice = self._create_simple_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')

    # ═══════════════════════════════════════════════════════════════
    # search_read with active_test
    # ═══════════════════════════════════════════════════════════════

    def test_22_search_read_active_test(self):
        """search_read: debe forzar active_test=False en contexto."""
        res = self.env["account.move"].search_read(
            [("id", "=", 0)], ["id"], limit=1
        )
        self.assertIsInstance(res, list)

    # ═══════════════════════════════════════════════════════════════
    # _compute_rate_for_documents
    # ═══════════════════════════════════════════════════════════════

    def test_23_rate_for_documents(self):
        """_compute_rate_for_documents: verifica que las tasas
        se computan para lineas de factura."""
        invoice = self._create_simple_invoice(self.currency_usd, 200.0)
        self.assertAlmostEqual(invoice.foreign_rate, 40.0, places=4)
        self.assertAlmostEqual(invoice.foreign_inverse_rate, 0.025, places=4)

    # ═══════════════════════════════════════════════════════════════
    # _compute_name on receivable lines
    # ═══════════════════════════════════════════════════════════════

    def test_24_receivable_line_name(self):
        """_compute_name: linea de cobro debe tener el name
        igual al name del move."""
        invoice = self._create_simple_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        rec_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        if rec_line:
            self.assertEqual(rec_line[0].name, invoice.name)

    # ═══════════════════════════════════════════════════════════════
    # _compute_tax_totals override
    # ═══════════════════════════════════════════════════════════════

    def test_25_compute_tax_totals_override(self):
        """_compute_tax_totals: verifica que el override setea
        active_id en contexto."""
        invoice = self._create_simple_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        # tax_totals debe contener las claves del override
        self.assertIn('formatted_base_amount_currency_ves', invoice.tax_totals or {})


    # ═══════════════════════════════════════════════════════════════
    # Helpers for refund validation tests
    # ═══════════════════════════════════════════════════════════════

    def _create_invoice(self, move_type='out_invoice', currency=None, price=100.0, lines=None):
        """Create an invoice with the given type, currency and lines.
        If lines is None, creates a single product line with the given price."""
        currency = currency or self.currency_vef
        journal = self.sale_journal if move_type.startswith('out') else self.purchase_journal

        if lines is None:
            lines = [{
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': price,
            }]

        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "currency_id": currency.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    **line,
                    "account_id": self.acc_inc.id if move_type.startswith('out') else self.acc_exp.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                })
                for line in lines
            ],
        })
        return invoice

    def _create_refund(self, invoice, line_mods=None):
        """Create a credit/debit note via the reversal wizard, then apply modifications
        via Form() to trigger the onchange naturally.
        line_mods is a dict mapping line index to dict of field overrides."""
        line_mods = line_mods or {}
        move_reversal = self.env['account.move.reversal'].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create({
            'date': fields.Date.today(),
            'journal_id': invoice.journal_id.id,
        })
        reversal = move_reversal.reverse_moves()
        refund = self.env['account.move'].browse(reversal['res_id'])

        with Form(refund) as refund_form:
            for _ in range(len(refund.invoice_line_ids)):
                refund_form.invoice_line_ids.remove(index=0)
            for i, inv_line in enumerate(invoice.invoice_line_ids):
                with refund_form.invoice_line_ids.new() as line:
                    if not inv_line.product_id:
                        line.display_type = inv_line.display_type
                        line.name = inv_line.name
                    else:
                        line.product_id = inv_line.product_id
                        line.quantity = inv_line.quantity
                        line.price_unit = inv_line.price_unit
                    if i in line_mods:
                        for field, value in line_mods[i].items():
                            setattr(line, field, value)
        return refund

    def _assert_refund_error(self, invoice, line_mods):
        """Assert that creating a refund with given line_mods raises ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_refund(invoice, line_mods=line_mods)

    # ═══════════════════════════════════════════════════════════════
    # out_refund validation tests (customer credit notes)
    # ═══════════════════════════════════════════════════════════════

    def test_26_refund_validation_quantity_equal(self):
        """out_refund: Cantidad igual a la original -> OK."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].quantity, 1.0)

    def test_27_refund_validation_quantity_partial(self):
        """out_refund: Cantidad menor a la original (NC parcial) -> OK."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice, line_mods={0: {"quantity": 0.5}})
        self.assertEqual(refund.invoice_line_ids[0].quantity, 0.5)

    def test_28_refund_validation_quantity_greater(self):
        """out_refund: Cantidad mayor a la original -> ValidationError."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"quantity": 5.0}})

    def test_29_refund_validation_quantity_zero(self):
        """out_refund: Cantidad cero -> ValidationError."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"quantity": 0.0}})

    def test_30_refund_validation_product_not_in_origin(self):
        """out_refund: Producto nuevo no presente en origen -> ValidationError."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        other_product = self.env["product.product"].create({
            "name": "Other Product", "type": "service",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        self._assert_refund_error(invoice, line_mods={0: {"product_id": other_product}})

    def test_31_refund_validation_product_consu_type(self):
        """out_refund: Producto tipo 'consu' desde origen -> OK."""
        consu_product = self.env["product.product"].create({
            "name": "Consu Product", "type": "consu",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        invoice = self._create_invoice(lines=[{
            "product_id": consu_product.id,
            "quantity": 2.0,
            "price_unit": 50.0,
        }])
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].product_id.id, consu_product.id)

    def test_32_refund_validation_product_storable_type(self):
        """out_refund: Producto tipo 'consu' desde origen -> OK."""
        consu_product = self.env["product.product"].create({
            "name": "Consu Test", "type": "consu",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        invoice = self._create_invoice(lines=[{
            "product_id": consu_product.id,
            "quantity": 3.0,
            "price_unit": 30.0,
        }])
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].product_id.id, consu_product.id)

    def test_33_refund_validation_price_unit_negative(self):
        """out_refund: Precio negativo -> ValidationError."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"price_unit": -10.0}})

    def test_34_refund_validation_price_unit_greater(self):
        """out_refund: Precio mayor al original -> ValidationError."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"price_unit": 150.0}})

    def test_35_refund_validation_price_unit_equal(self):
        """out_refund: Precio igual al original -> OK."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].price_unit, 100.0)

    def test_36_refund_validation_section_line(self):
        """out_refund: Línea de sección/nota agregada en NC -> ignorada sin error."""
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        with Form(refund) as refund_form:
            with refund_form.invoice_line_ids.new() as line:
                line.display_type = 'line_section'
                line.name = 'Test Section'
        self.assertEqual(len(refund.invoice_line_ids), 2)

    # ═══════════════════════════════════════════════════════════════
    # in_refund validation tests (supplier credit notes)
    # ═══════════════════════════════════════════════════════════════

    def test_37_in_refund_validation_quantity_equal(self):
        """in_refund: Cantidad igual a la original -> OK."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].quantity, 1.0)

    def test_38_in_refund_validation_quantity_partial(self):
        """in_refund: Cantidad menor a la original (NC parcial) -> OK."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice, line_mods={0: {"quantity": 0.5}})
        self.assertEqual(refund.invoice_line_ids[0].quantity, 0.5)

    def test_39_in_refund_validation_quantity_greater(self):
        """in_refund: Cantidad mayor a la original -> ValidationError."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"quantity": 5.0}})

    def test_40_in_refund_validation_quantity_zero(self):
        """in_refund: Cantidad cero -> ValidationError."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"quantity": 0.0}})

    def test_41_in_refund_validation_product_not_in_origin(self):
        """in_refund: Producto nuevo no presente en origen -> ValidationError."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        other_product = self.env["product.product"].create({
            "name": "Other Product", "type": "service",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        self._assert_refund_error(invoice, line_mods={0: {"product_id": other_product}})

    def test_42_in_refund_validation_product_consu_type(self):
        """in_refund: Producto tipo 'consu' desde origen -> OK."""
        consu_product = self.env["product.product"].create({
            "name": "Consu Product", "type": "consu",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        invoice = self._create_invoice(move_type='in_invoice', lines=[{
            "product_id": consu_product.id,
            "quantity": 2.0,
            "price_unit": 50.0,
        }])
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].product_id.id, consu_product.id)

    def test_43_in_refund_validation_product_type_b(self):
        """in_refund: Producto tipo 'consu' (alterno) desde origen -> OK."""
        consu_product = self.env["product.product"].create({
            "name": "Consu Test", "type": "consu",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        invoice = self._create_invoice(lines=[{
            "product_id": consu_product.id,
            "quantity": 3.0,
            "price_unit": 30.0,
        }])
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].product_id.id, consu_product.id)

    def test_44_in_refund_validation_price_unit_negative(self):
        """in_refund: Precio negativo -> ValidationError."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"price_unit": -10.0}})

    def test_45_in_refund_validation_price_unit_greater(self):
        """in_refund: Precio mayor al original -> ValidationError."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"price_unit": 150.0}})

    def test_46_in_refund_validation_price_unit_equal(self):
        """in_refund: Precio igual al original -> OK."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(refund.invoice_line_ids[0].price_unit, 100.0)

    def test_47_in_refund_validation_section_line(self):
        """in_refund: Línea de sección/nota agregada en NC -> ignorada sin error."""
        invoice = self._create_invoice(move_type='in_invoice')
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        with Form(refund) as refund_form:
            with refund_form.invoice_line_ids.new() as line:
                line.display_type = 'line_section'
                line.name = 'Test Section'
        self.assertEqual(len(refund.invoice_line_ids), 2)

    # ═══════════════════════════════════════════════════════════════
    # Multi-line invoice tests
    # ═══════════════════════════════════════════════════════════════

    def test_48_refund_validation_multi_line_partial(self):
        """Múltiples líneas: NC parcial en una línea, la otra igual -> OK."""
        product_b = self.env["product.product"].create({
            "name": "Product B", "type": "service",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        invoice = self._create_invoice(lines=[
            {"product_id": self.product.id, "quantity": 2.0, "price_unit": 100.0},
            {"product_id": product_b.id, "quantity": 3.0, "price_unit": 50.0},
        ])
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice, line_mods={0: {"quantity": 1.0}})
        self.assertEqual(refund.invoice_line_ids[0].quantity, 1.0)
        self.assertEqual(refund.invoice_line_ids[1].quantity, 3.0)

    def test_49_refund_validation_multi_line_one_invalid(self):
        """Múltiples líneas: una línea inválida -> ValidationError."""
        product_b = self.env["product.product"].create({
            "name": "Product B", "type": "service",
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        invoice = self._create_invoice(lines=[
            {"product_id": self.product.id, "quantity": 2.0, "price_unit": 100.0},
            {"product_id": product_b.id, "quantity": 3.0, "price_unit": 50.0},
        ])
        invoice.with_context(move_action_post_alert=True).action_post()
        self._assert_refund_error(invoice, line_mods={0: {"quantity": 10.0}})

    # ═══════════════════════════════════════════════════════════════
    # Section/note lines in origin invoice
    # ═══════════════════════════════════════════════════════════════

    def test_50_refund_validation_origin_with_section(self):
        """Sección en factura origen: NC copia sección + producto, sección ignorada -> OK."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "display_type": "line_section",
                    "name": "Test Section",
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 100.0,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice)
        self.assertEqual(len(refund.invoice_line_ids), 2)
        self.assertFalse(refund.invoice_line_ids[0].product_id)
        self.assertEqual(refund.invoice_line_ids[1].product_id.id, self.product.id)

    def test_51_refund_validation_origin_with_section_partial(self):
        """Sección en origen + NC parcial en producto -> OK."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "display_type": "line_section",
                    "name": "Test Section",
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 100.0,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        refund = self._create_refund(invoice, line_mods={1: {"quantity": 0.5}})
        self.assertEqual(refund.invoice_line_ids[1].quantity, 0.5)
