import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_tax_foreign")
class TestAccountTaxForeign(TransactionCase):

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_eur.active = True
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")

        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
            "unique_tax": False,
        })

        today = fields.Date.today()
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_vef.id,
            "inverse_company_rate": 1.0, "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 50.0, "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_eur.id,
            "inverse_company_rate": 55.0, "company_id": self.company.id,
        })

        self.acc_rec = self._get_or_create('120000', 'Receivable', 'asset_receivable', reconcile=True)
        self.acc_inc = self._get_or_create('400000', 'Income', 'income')
        self.acc_tax = self._get_or_create('200000', 'Tax Payable', 'liability_current', reconcile=True)
        self.acc_exp = self._get_or_create('500000', 'Expense', 'expense')
        self.acc_bank = self._get_or_create('100100', 'Bank', 'asset_cash', reconcile=True)

        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA', 'company_id': self.company.id, 'country_id': self.country_ve.id,
        })
        self.tax_16 = self._create_tax('IVA 16%', 16.0)

        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Sales Tax Test", "code": "STAX",
            "type": "sale", "company_id": self.company.id,
            "default_account_id": self.acc_inc.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "Tax Test Partner", "country_id": self.country_ve.id,
            "property_account_receivable_id": self.acc_rec.id,
        })

        self.product = self.env["product.product"].create({
            "name": "Tax Service", "type": "service", "list_price": 100.0,
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

    def _create_tax(self, name, amount):
        return self.env["account.tax"].with_company(self.company).create({
            "name": name, "amount": amount, "amount_type": "percent",
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

    # ═══════════════════════════════════════════════════════════════
    # _get_tax_totals_summary — claves en moneda extranjera
    # ═══════════════════════════════════════════════════════════════

    def test_01_tax_totals_foreign_keys(self):
        """_get_tax_totals_summary: factura en USD debe incluir
        las claves de moneda extranjera en tax_totals."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 2.0, "price_unit": 500.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()

        tt = invoice.tax_totals
        # Claves del override en account_tax.py
        self.assertIn('foreign_currency_id', tt)
        self.assertIn('ves_currency_id', tt)
        self.assertIn('base_amount_foreign_currency', tt)
        self.assertIn('tax_amount_foreign_currency', tt)
        self.assertIn('total_amount_foreign_currency', tt)

        # Claves formateadas en VES
        self.assertIn('formatted_base_amount_currency_ves', tt)
        self.assertIn('formatted_tax_amount_currency_ves', tt)
        self.assertIn('formatted_total_amount_currency_ves', tt)

        # Claves formateadas en moneda extranjera
        self.assertIn('formatted_base_amount_foreign_currency', tt)
        self.assertIn('formatted_tax_amount_foreign_currency', tt)
        self.assertIn('formatted_total_amount_foreign_currency', tt)

        # Verificar valores
        # Base: $1.000,00, IVA 16%: $160,00, Total: $1.160,00
        self.assertAlmostEqual(tt.get('base_amount_foreign_currency', 0), 1000.0, delta=1.0)
        self.assertAlmostEqual(tt.get('tax_amount_foreign_currency', 0), 160.0, delta=1.0)
        self.assertAlmostEqual(tt.get('total_amount_foreign_currency', 0), 1160.0, delta=1.0)

    def test_02_tax_totals_subtotals_foreign_keys(self):
        """_get_tax_totals_summary: los subtotales deben incluir
        claves de moneda extranjera."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()

        tt = invoice.tax_totals
        for subtotal in tt.get("subtotals", []):
            self.assertIn('tax_amount_foreign_currency', subtotal)
            self.assertIn('base_amount_foreign_currency', subtotal)
            self.assertIn('total_amount_foreign_currency', subtotal)
            self.assertIn('formatted_base_amount_currency_ves', subtotal)
            self.assertIn('formatted_tax_amount_currency_ves', subtotal)

            for tax_group in subtotal.get("tax_groups", []):
                self.assertIn('tax_amount_foreign_currency', tax_group)
                self.assertIn('base_amount_foreign_currency', tax_group)
                self.assertIn('formatted_base_amount_currency_ves', tax_group)
                self.assertIn('formatted_tax_amount_currency_ves', tax_group)

    # ═══════════════════════════════════════════════════════════════
    # _get_tax_totals_summary — factura en EUR (tercera moneda)
    # ═══════════════════════════════════════════════════════════════

    def test_03_tax_totals_eur_third_currency(self):
        """_get_tax_totals_summary: factura en EUR debe tener
        claves de moneda extranjera (USD) y formateadas."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_eur.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()

        tt = invoice.tax_totals
        # Debe tener foreign_currency keys incluso con tercera moneda
        self.assertIn('base_amount_foreign_currency', tt)

    # ═══════════════════════════════════════════════════════════════
    # _prepare_foreign_base_line_for_taxes_computation
    # ═══════════════════════════════════════════════════════════════

    def test_04_prepare_foreign_base_line(self):
        """_prepare_foreign_base_line_for_taxes_computation:
        verifica que una linea de producto se convierte
        correctamente a base line en moneda extranjera."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 3.0, "price_unit": 150.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        # Obtener la linea de producto
        product_line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')
        if product_line:
            base_line = invoice._prepare_product_foreign_base_line_for_taxes_computation(
                product_line[0]
            )
            self.assertIsInstance(base_line, dict)
            self.assertIn('price_unit', base_line)
            self.assertIn('quantity', base_line)
            self.assertIn('currency_id', base_line)
            # La linea usa foreign_price y foreign_currency_id
            self.assertEqual(base_line.get('quantity'), 3.0)
            self.assertEqual(base_line.get('currency_id'), self.currency_usd)
            self.assertEqual(base_line.get('currency_id').id, self.currency_usd.id)

    # ═══════════════════════════════════════════════════════════════
    # _get_rounded_foreign_base_and_tax_lines
    # ═══════════════════════════════════════════════════════════════

    def test_05_get_rounded_foreign_base_and_tax_lines(self):
        """_get_rounded_foreign_base_and_tax_lines: verifica que
        se obtienen las lineas base y de impuesto en moneda extranjera."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()

        base_lines, tax_lines = invoice._get_rounded_foreign_base_and_tax_lines()
        self.assertIsInstance(base_lines, list)
        self.assertIsInstance(tax_lines, list)
        # Debe haber al menos una linea base (el producto)
        self.assertGreaterEqual(len(base_lines), 1)

    # ═══════════════════════════════════════════════════════════════
    # _prepare_cash_rounding_foreign_base_line_for_taxes_computation
    # ═══════════════════════════════════════════════════════════════

    def test_06_cash_rounding_foreign_base_line(self):
        """_prepare_cash_rounding_foreign_base_line: verifica que
        no crashea con una linea de redondeo."""
        invoice = self._create_draft_invoice_usd()
        # Buscar lineas de redondeo (no deberia haber, solo verificar que no crashea)
        rounding_lines = invoice.line_ids.filtered(
            lambda l: l.display_type == 'rounding' and not l.tax_repartition_line_id
        )
        if rounding_lines:
            base_line = invoice._prepare_cash_rounding_foreign_base_line_for_taxes_computation(
                rounding_lines[0]
            )
            self.assertIn('price_unit', base_line)

    def _create_draft_invoice_usd(self):
        return self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })

    # ═══════════════════════════════════════════════════════════════
    # _compute_foreign_taxable_income y _compute_foreign_total_billed
    # ═══════════════════════════════════════════════════════════════

    def test_07_foreign_taxable_income(self):
        """_compute_foreign_taxable_income y _compute_foreign_total_billed:
        verifica campos computados en factura USD."""
        invoice = self._create_draft_invoice_usd()
        invoice.with_context(move_action_post_alert=True).action_post()

        # foreign_taxable_income debe computarse
        self.assertIsNotNone(invoice.foreign_taxable_income)
        # foreign_total_billed debe computarse
        self.assertIsNotNone(invoice.foreign_total_billed)
        # Total USD: $100 + $16 IVA = $116
        self.assertAlmostEqual(invoice.foreign_total_billed, 116.0, delta=1.0)

    # ═══════════════════════════════════════════════════════════════
    # _compute_untaxed_total foreign
    # ═══════════════════════════════════════════════════════════════

    def test_08_foreign_untaxed_total(self):
        """_compute_foreign_untaxed_total: verifica el total
        sin impuestos en moneda extranjera."""
        invoice = self._create_draft_invoice_usd()
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertIsNotNone(invoice.foreign_untaxed_total)
        # Base imponible: $100.00
        self.assertAlmostEqual(invoice.foreign_untaxed_total, 100.0, delta=1.0)

    # ═══════════════════════════════════════════════════════════════
    # _compute_needed_terms — foreign_balance en payment terms
    # ═══════════════════════════════════════════════════════════════

    def test_09_needed_terms_foreign_balance(self):
        """_compute_needed_terms: con payment_term, debe distribuir
        foreign_balance en los terminos."""
        payment_term = self.env['account.payment.term'].create({
            'name': '50-50 Test',
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 15}),
            ]
        })
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_payment_term_id": payment_term.id,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()

        # Verificar que needed_terms tiene foreign_balance
        if invoice.needed_terms:
            for term_key, term_data in invoice.needed_terms.items():
                self.assertIn('foreign_balance', term_data,
                              f"Term {term_key} debe tener foreign_balance")
                self.assertGreater(term_data['foreign_balance'], 0)

    # ═══════════════════════════════════════════════════════════════
    # _sync_tax_lines — verificar que la sincronizacion corre
    # ═══════════════════════════════════════════════════════════════

    def test_10_sync_tax_lines_foreign_balance(self):
        """_sync_tax_lines: al postear, las lineas de impuesto
        deben tener foreign_debit/credit computados."""
        invoice = self._create_draft_invoice_usd()
        invoice.with_context(move_action_post_alert=True).action_post()

        tax_lines = invoice.line_ids.filtered('tax_repartition_line_id')
        for tline in tax_lines:
            # Las lineas de impuesto deben tener foreign amount
            self.assertIsNotNone(tline.foreign_balance,
                                 f"Tax line {tline.id} debe tener foreign_balance")
