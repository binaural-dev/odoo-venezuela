
import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_accountant_test")
class TestForeignBalance(TransactionCase):

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_eur.active = True
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")
        
        # Configure company: Base VEF, Foreign USD
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "account_fiscal_country_id": self.country_ve.id,
                "country_id": self.country_ve.id,
            }
        )
        
        # Setup rates
        # Company Currency is now VEF.
        # Rates should be:
        # VEF = 1.0 (Base)
        # USD = 0.025 (inverse of 40) if using Odoo standard rate (Unit per Base).
        # We are using `inverse_company_rate` field which implies "Company Currency per Unit".
        # If so: 
        # VEF: 1.0
        # USD: 40.0 (40 VEF for 1 USD)
        
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_vef.id,
                "inverse_company_rate": 1.0, 
                "company_id": self.company.id,
            }
        )
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_usd.id,
                "inverse_company_rate": 40.0, # 1 USD = 40 VEF
                "company_id": self.company.id,
            }
        )
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_eur.id,
                "inverse_company_rate": 44.0, # 1 EUR = 44 VEF (example: 1.1 * 40 presumably) 
                "company_id": self.company.id,
            }
        )

        self.account_receivable = self.env['account.account'].search([('code', '=', '120000'), ('company_ids', 'in', self.company.id)], limit=1)
        if not self.account_receivable:
            self.account_receivable = self.env['account.account'].create({
                'name': 'Receivable',
                'code': '120000',
                'account_type': 'asset_receivable',
                'company_ids': [(6, 0, [self.company.id])],
                'reconcile': True,
            })

        self.account_income = self.env['account.account'].search([('code', '=', '400000'), ('company_ids', 'in', self.company.id)], limit=1)
        if not self.account_income:
            self.account_income = self.env['account.account'].create({
                'name': 'Income',
                'code': '400000',
                'account_type': 'income',
                'company_ids': [(6, 0, [self.company.id])],
            })

        self.test_tax_group = self.env['account.tax.group'].create({
            'name': 'Test Tax Group',
            'company_id': self.company.id,
            'country_id': self.country_ve.id,
        })

        self.account_tax = self.env['account.account'].search([('code', '=', '200000'), ('company_ids', 'in', self.company.id)], limit=1)
        if not self.account_tax:
            self.account_tax = self.env['account.account'].create({
                'name': 'Tax Paid',
                'code': '200000',
                'account_type': 'liability_current',
                'company_ids': [(6, 0, [self.company.id])],
            })
        
        self.test_tax = self.env["account.tax"].create({
            "name": "Test Tax 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.test_tax_group.id,
        })

        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create(
            {
                "name": "Sales Test",
                "code": "SLTST",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self.account_income.id,
            }
        )
    
        # Partner created with VEF company country (Venezuela)
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.country_ve.id,
                "property_account_receivable_id": self.account_receivable.id,
            }
        )
        
        self.product = self.env["product.product"].create(
            {
                "name": "Product Test",
                "type": "service",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [self.test_tax.id])],
            }
        )

    def test_invoice_foreign_balance_simple(self):
        """Testea el balance de débito/crédito en divisa extranjera (USD) para una factura."""
        # Create invoice in USD (Foreign Currency now)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_usd.id, 
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0, # 100 USD
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice.state, 'posted', "Invoice failed to post")
        
        for line in invoice.line_ids:
             _logger.info(f"Line: {line.name} | Type: {line.display_type} | Account: {line.account_id.name} | Debit: {line.debit} | Credit: {line.credit} | Foreign Debit: {line.foreign_debit} | Foreign Credit: {line.foreign_credit}")

        sum_foreign_debit = sum(invoice.line_ids.mapped('foreign_debit'))
        sum_foreign_credit = sum(invoice.line_ids.mapped('foreign_credit'))
        
        # Verify balance
        self.assertAlmostEqual(sum_foreign_debit, sum_foreign_credit, places=2, msg="Foreign Debit/Credit must balance")
        self.assertGreater(sum_foreign_debit, 0)
        
        # Expectation: 100 USD Base + 16 USD Tax = 116.0 USD Total
        self.assertAlmostEqual(sum_foreign_debit, 116.0, delta=1.0, msg="Foreign Amount should be 116 USD")
        

    def test_invoice_foreign_balance_company_currency(self):
        """ Test foreign debit/credit balance on an invoice in Company Currency (VEF).
            Foreign Balance should be calculated based on the rate.
        """
        # Create invoice in VEF (Company Currency now)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_vef.id, 
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 4000.0, # 4000 VEF
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice.state, 'posted')
        
        for line in invoice.line_ids:
             _logger.info(f"Line: {line.name} | Type: {line.display_type} | Account: {line.account_id.name} | Debit: {line.debit} | Credit: {line.credit} | Foreign Debit: {line.foreign_debit} | Foreign Credit: {line.foreign_credit}")

        sum_foreign_debit = sum(invoice.line_ids.mapped('foreign_debit'))
        sum_foreign_credit = sum(invoice.line_ids.mapped('foreign_credit'))
        
        self.assertAlmostEqual(sum_foreign_debit, sum_foreign_credit, places=2)
        
        # 4000 VEF + 16% Tax = 4640 VEF.
        # Rate: 40 VEF = 1 USD.
        # 4640 / 40 = 116.0 USD.
        self.assertAlmostEqual(sum_foreign_debit, 116.0, delta=1.0, msg="Foreign Amount (USD) should be 116")

    def test_invoice_pricelist_eur(self):
        """ Test invoice line using a 3rd currency (EUR) """
        
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_eur.id, # Invoice in EUR
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0, # 100 EUR
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice.state, 'posted', "Invoice failed to post")

        for line in invoice.line_ids:
             _logger.info(f"Line: {line.name} | Type: {line.display_type} | Account: {line.account_id.name} | Debit: {line.debit} | Credit: {line.credit} | Foreign Debit: {line.foreign_debit} | Foreign Credit: {line.foreign_credit}")

        sum_foreign_debit = sum(invoice.line_ids.mapped('foreign_debit'))
        sum_foreign_credit = sum(invoice.line_ids.mapped('foreign_credit'))
        
        self.assertAlmostEqual(sum_foreign_debit, sum_foreign_credit, places=2)
        
        # Calculation:
        # 100 EUR.
        # Target Foreign Currency is USD.
        # Base is VEF.
        # 100 EUR -> VEF. Rate: 1 EUR = 44 VEF.
        # 100 EUR = 4400 VEF.
        # Then VEF -> USD. Rate: 40 VEF = 1 USD.
        # 4400 / 40 = 110 USD.
        
        # Tax is 16%. 
        # Base: 4400 VEF. Tax: 704 VEF. Total: 5104 VEF.
        # 5104 VEF / 40 = 127.6 USD.
        
        self.assertGreater(sum_foreign_debit, 0)
        self.assertAlmostEqual(sum_foreign_debit, 127.6, delta=5.0)

    def test_payment_foreign_balance_usd(self):
        """ Test foreign debit/credit balance on a payment for a foreign currency invoice. """
        
        # Create Bank Journal in USD
        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), 
            ('currency_id', '=', self.currency_usd.id),
            ('company_id', '=', self.company.id)
        ], limit=1)
        
        if not bank_journal:
            bank_journal = self.env['account.journal'].sudo().create({
                'name': 'Bank USD',
                'type': 'bank',
                'code': 'BNKUSD',
                'currency_id': self.currency_usd.id,
                'company_id': self.company.id,
            })

        # Create invoice in USD
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_usd.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0, # 100 USD
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice.state, 'posted', "Invoice failed to post")
        self.assertAlmostEqual(invoice.amount_total, 116.0, msg="Invoice Total should be 116.0 USD")

        # Register Payment
        payment_register = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'journal_id': bank_journal.id,
            'amount': 116.0,
            'currency_id': self.currency_usd.id,
            'payment_date': fields.Date.today(),
        })
        payment = payment_register._create_payments()
        _logger.info("Payment: %s", payment)
        self.assertIn(payment.state, ['posted', 'paid'], "Payment failed to post")
        
        # Check Payment Move Lines
        move = payment.move_id
        _logger.info("PAYMENT MOVE LINES:")
        for line in move.line_ids:
             _logger.info(f"Payment Line: {line.name} | Account: {line.account_id.name} | Debit: {line.debit} | Credit: {line.credit} | Foreign Debit: {line.foreign_debit} | Foreign Credit: {line.foreign_credit}")

        sum_foreign_debit = sum(move.line_ids.mapped('foreign_debit'))
        sum_foreign_credit = sum(move.line_ids.mapped('foreign_credit'))
        
        self.assertAlmostEqual(sum_foreign_debit, sum_foreign_credit, places=2, msg="Payment Foreign Debit/Credit must balance")
        self.assertGreater(sum_foreign_debit, 0, "Foreign Amount should be greater than 0")
        
        # Verify conversion rate logic using Odoo's _convert:
        # foreign_debit/credit should be debit/credit converted to foreign_currency_id using payment date rate.
        
        for line in move.line_ids:
            if line.debit > 0:
                # Convert VEF (Debit) -> USD (Foreign Debit)
                expected_foreign_debit = self.currency_vef._convert(
                    line.debit, 
                    self.currency_usd, 
                    self.company, 
                    payment.date
                )
                # Allow small rounding differences
                self.assertAlmostEqual(line.foreign_debit, expected_foreign_debit, delta=0.1, 
                                       msg=f"Line {line.name} Foreign Debit {line.foreign_debit} does not match converted Debit {line.debit}")
            
            if line.credit > 0:
                expected_foreign_credit = self.currency_vef._convert(
                    line.credit, 
                    self.currency_usd, 
                    self.company, 
                    payment.date
                )
                self.assertAlmostEqual(line.foreign_credit, expected_foreign_credit, delta=0.1, 
                                       msg=f"Line {line.name} Foreign Credit {line.foreign_credit} does not match converted Credit {line.credit}")


        # Overall total check
        self.assertAlmostEqual(sum_foreign_debit, 116.0, delta=1.0, msg="Payment Foreign Amount should be 116 USD")



    def test_payment_foreign_balance_vef(self):
        """ Test foreign debit/credit balance on a payment in VEF (Company Currency) for a foreign currency invoice (USD). """
        
        # Create Bank Journal in VEF
        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), 
            ('currency_id', '=', self.currency_vef.id),
            ('company_id', '=', self.company.id)
        ], limit=1)
        
        if not bank_journal:
            bank_journal = self.env['account.journal'].sudo().create({
                'name': 'Bank VEF',
                'type': 'bank',
                'code': 'BNKVEF',
                'currency_id': self.currency_vef.id,
                'company_id': self.company.id,
            })

        # Create invoice in USD
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_usd.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0, # 100 USD
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            } 
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice.state, 'posted', "Invoice failed to post")
        self.assertAlmostEqual(invoice.amount_total, 116.0, msg="Invoice Total should be 116.0 USD")

        # Prepare Payment Amount in VEF
        # Invoice is 116 USD. Rate 1 USD = 40 VEF.
        # Payment should be 4640 VEF.
        amount_vef = self.currency_usd._convert(
            116.0,
            self.currency_vef,
            self.company,
            fields.Date.today()
        )

        # Register Payment in VEF
        payment_register = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'journal_id': bank_journal.id,
            'amount': amount_vef,
            'currency_id': self.currency_vef.id,
            'payment_date': fields.Date.today(),
        })
        payment = payment_register._create_payments()
        
        self.assertIn(payment.state, ['posted', 'paid'], "Payment failed to post")
        
        # Check Payment Move Lines
        move = payment.move_id
        for line in move.line_ids:
             _logger.info(f"Payment Line: {line.name} | Account: {line.account_id.name} | Debit: {line.debit} | Credit: {line.credit} | Foreign Debit: {line.foreign_debit} | Foreign Credit: {line.foreign_credit}")

        sum_foreign_debit = sum(move.line_ids.mapped('foreign_debit'))
        
        # Verification
        # Payment is in VEF.
        # Foreign Currency is USD.
        # Move Lines will have Debit/Credit in VEF.
        # Foreign Debit/Credit should be the VEF amount converted to USD.
        
        # We expect foreign balance to match the original USD invoice amount (116.0) approximately.
        self.assertAlmostEqual(sum_foreign_debit, 116.0, delta=1.0, msg="Payment Foreign Amount should be approx 116 USD")
        
        for line in move.line_ids:
            if line.debit > 0:
                # Convert VEF (Debit) -> USD (Foreign Debit)
                expected_foreign_debit = self.currency_vef._convert(
                    line.debit, 
                    self.currency_usd, 
                    self.company, 
                    payment.date
                )
                self.assertAlmostEqual(line.foreign_debit, expected_foreign_debit, delta=0.5, 
                                       msg=f"Line {line.name} Foreign Debit {line.foreign_debit} does not match converted Debit {line.debit}")
            
            if line.credit > 0:
                expected_foreign_credit = self.currency_vef._convert(
                    line.credit, 
                    self.currency_usd, 
                    self.company, 
                    payment.date
                )
                self.assertAlmostEqual(line.foreign_credit, expected_foreign_credit, delta=0.5, 
                                       msg=f"Line {line.name} Foreign Credit {line.foreign_credit} does not match converted Credit {line.credit}")

    def test_payment_foreign_balance_eur(self):
        """ Test foreign debit/credit balance on a payment in EUR for a foreign currency invoice (USD). """
        
        # Create Bank Journal in EUR
        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), 
            ('currency_id', '=', self.currency_eur.id),
            ('company_id', '=', self.company.id)
        ], limit=1)
        
        if not bank_journal:
            bank_journal = self.env['account.journal'].sudo().create({
                'name': 'Bank EUR',
                'type': 'bank',
                'code': 'BNKEUR',
                'currency_id': self.currency_eur.id,
                'company_id': self.company.id,
            })

        # Create invoice in USD
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_usd.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0, # 100 USD
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            } 
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice.state, 'posted', "Invoice failed to post")
        self.assertAlmostEqual(invoice.amount_total, 116.0, msg="Invoice Total should be 116.0 USD")

        # Prepare Payment Amount in EUR
        # Invoice is 116 USD. 
        # Convert USD -> EUR (via VEF)
        amount_eur = self.currency_usd._convert(
            116.0,
            self.currency_eur,
            self.company,
            fields.Date.today()
        )

        # Register Payment in EUR
        payment_register = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'journal_id': bank_journal.id,
            'amount': amount_eur,
            'currency_id': self.currency_eur.id,
            'payment_date': fields.Date.today(),
        })
        payment = payment_register._create_payments()
        
        # In some envs state might be 'in_process', handle it or just check it is not draft/cancelled
        self.assertIn(payment.state, ['posted', 'paid', 'in_process'], "Payment failed to post")
        
        # Check Payment Move Lines
        move = payment.move_id

        sum_foreign_debit = sum(move.line_ids.mapped('foreign_debit'))
        
        # Verification
        # Payment is in EUR.
        # Foreign Currency Config is USD.
        # We expect foreign balance to match the original USD invoice amount (116.0) approximately.
        self.assertAlmostEqual(sum_foreign_debit, 116.0, delta=1.0, msg="Payment Foreign Amount should be approx 116 USD")
        
        for line in move.line_ids:
            if line.debit > 0:
                # Convert VEF (Debit) -> USD (Foreign Debit)
                expected_foreign_debit = self.currency_vef._convert(
                    line.debit, 
                    self.currency_usd, 
                    self.company, 
                    payment.date
                )
                self.assertAlmostEqual(line.foreign_debit, expected_foreign_debit, delta=0.5, 
                                       msg=f"Line {line.name} Foreign Debit {line.foreign_debit} does not match converted Debit {line.debit}")
            
            if line.credit > 0:
                expected_foreign_credit = self.currency_vef._convert(
                    line.credit, 
                    self.currency_usd, 
                    self.company, 
                    payment.date
                )
                self.assertAlmostEqual(line.foreign_credit, expected_foreign_credit, delta=0.5, 
                                       msg=f"Line {line.name} Foreign Credit {line.foreign_credit} does not match converted Credit {line.credit}")

    def test_invoice_foreign_balance_low_amount_extreme_rate(self):
        """
        Reproduces the bug: invoice in VEF (company currency) for 1 VEF with 16% tax
        and a rate of 431.01 VEF per USD (written as 431,010000000000 in Venezuelan notation).

        With this rate, 1 VEF = ~0.00232 USD, so the tax (0.16 VEF) converts
        to ~0.000371 USD which rounds to $0.00 with 2 decimal places.

        Without the fix, _round_base_lines_tax_details re-uses the tax line's
        amount_currency (in VEF = -0.16) for the foreign calculation, causing
        foreign_balance to be set to -0.16 VEF as if it were USD.

        Expected behavior after fix:
         - sum(foreign_debit) == sum(foreign_credit)  (internally consistent)
         - Tax line foreign_credit must NOT equal its VEF credit value (0.16)
        """
        # 431,010000000000 in Venezuelan notation = 431.01 VEF per USD
        extreme_rate = 431.01
        rate = self.env["res.currency.rate"].search([
            ("name", "=", fields.Date.today()),
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ])
        if rate:
            rate.write({"inverse_company_rate": extreme_rate})
        else:
            self.env["res.currency.rate"].create(
                {
                    "name": fields.Date.today(),
                    "currency_id": self.currency_usd.id,
                    "inverse_company_rate": extreme_rate,
                    "company_id": self.company.id,
                }
            )

        purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create(
            {
                "name": "Purchase Test Extreme",
                "code": "PRTEX",
                "type": "purchase",
                "company_id": self.company.id,
            }
        )

        purchase_tax = self.env["account.tax"].create({
            "name": "IVA 16% Compras Extreme",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
            "tax_group_id": self.test_tax_group.id,
        })

        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": purchase_journal.id,
                "currency_id": self.currency_vef.id,  # Invoice in VEF (company currency)
                "date": fields.Date.today(),
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 1.0,  # 1 VEF — small amount that exposes the bug
                            "account_id": self.account_income.id,
                            "tax_ids": [(6, 0, [purchase_tax.id])],
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertEqual(invoice.state, "posted", "Invoice failed to post")

        for line in invoice.line_ids:
            _logger.info(
                f"ExtremeRateTest | {line.display_type} | "
                f"Debit: {line.debit} | Credit: {line.credit} | "
                f"ForeignDebit: {line.foreign_debit} | ForeignCredit: {line.foreign_credit}"
            )

        sum_foreign_debit = sum(invoice.line_ids.mapped("foreign_debit"))
        sum_foreign_credit = sum(invoice.line_ids.mapped("foreign_credit"))

        # 1. Foreign debit and credit must balance
        self.assertAlmostEqual(
            sum_foreign_debit,
            sum_foreign_credit,
            places=6,
            msg="Foreign Debit/Credit must balance even with extreme rates",
        )

        # 2. No tax line should show its VEF credit as if it were USD.
        #    0.16 VEF tax line must NOT have foreign_credit == 0.16 (USD).
        for line in invoice.line_ids:
            if line.display_type == "tax" and line.credit > 0:
                self.assertNotAlmostEqual(
                    line.foreign_credit,
                    line.credit,
                    places=2,
                    msg=(
                        f"Tax line foreign_credit ({line.foreign_credit}) must not equal "
                        f"its VEF credit ({line.credit}). VEF value was used as USD (bug)."
                    ),
                )

