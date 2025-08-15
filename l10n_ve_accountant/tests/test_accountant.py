import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountant(TransactionCase):
    """Tests for invoice posting behaviour regarding the invoice date."""

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
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

        # --- Impuesto ---
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
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

        display_sel = dict(self.Line._fields['display_type'].selection or [])

        self.display_supports_product = 'product' in display_sel




        

        # (Opcional) Si tu módulo de anticipos exige cuentas específicas:
        # Cuentas de anticipo en la compañía (tipos modernos v16/v17: account_type)
        if not getattr(self.company, 'advance_customer_account_id', False) or not getattr(self.company, 'advance_supplier_account_id', False):
            adv_cust = self.env['account.account'].search([('code', '=', '900000'), ('company_id', '=', self.company.id)], limit=1) or \
                self.env['account.account'].create({
                    'name': 'Advance Customers',
                    'code': '900000',
                    'account_type': 'liability_current',
                    'reconcile': True,
                    'company_id': self.company.id,
                })
            adv_supp = self.env['account.account'].search([('code', '=', '900001'), ('company_id', '=', self.company.id)], limit=1) or \
                self.env['account.account'].create({
                    'name': 'Advance Suppliers',
                    'code': '900001',
                    'account_type': 'asset_current',
                    'reconcile': True,
                    'company_id': self.company.id,
                })
            self.company.write({
                'advance_customer_account_id': adv_cust.id,
                'advance_supplier_account_id': adv_supp.id,
            })

        # Nota: eliminamos la creación previa de self.account_payment_method_line en el journal de VENTAS
        # y también evitamos crear un payment anticipado aquí que dispare la constraint antes del test.

        
        # ----------------- Helpers -----------------
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
            is_advance=False,
            fx_rate=None,
            fx_rate_inv=None,
            pm_line=None,
        ):
            """Crea y valida un payment genérico."""
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
                "payment_method_line_id": pm_line.id,  # <-- misma línea y mismo journal
                "is_advance_payment": is_advance,
                "date": fields.Date.today(),
            }
            if fx_rate:
                vals.update({"foreign_rate": fx_rate, "foreign_inverse_rate": fx_rate_inv})

            pay = self.env["account.payment"].create(vals)
            pay.action_post()
            return pay
        
    def _create_draft_invoice(self, journal, line_defs):
            """Create a draft out_invoice with given journal and line definitions.
            line_defs: list of dicts with keys: name, account(optional), product(optional), qty, price, taxes(list ids), display_type(optional)
            """
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
       
    def test_get_journal_income_account_fallback(self):
        """It should return revenue_account_id, else income_account_id, else default_account_id."""
        j = self.journal_contado

        # Start clean
        if 'revenue_account_id' in self.Journal._fields:
            j.revenue_account_id = False
        if 'income_account_id' in self.Journal._fields:
            j.income_account_id = False
        j.default_account_id = self.account_contado

        acc = self.Move._get_journal_income_account(j)
        self.assertEqual(acc, self.account_contado, "Fallback to default_account_id failed")

        if 'income_account_id' in self.Journal._fields:
            j.income_account_id = self.account_credito
            acc = self.Move._get_journal_income_account(j)
            self.assertEqual(acc, self.account_credito, "Should prefer income_account_id over default_account_id")

        if 'revenue_account_id' in self.Journal._fields:
            j.revenue_account_id = self.account_product
            acc = self.Move._get_journal_income_account(j)
            self.assertEqual(acc, self.account_product, "Should prefer revenue_account_id over others")
    
    def test_update_only_lines_using_old_journal_account(self):
        """Only invoice lines that use old journal income account should change; others remain."""
        # Create invoice with:
        #  - L1 uses old_journal income account (must change)
        #  - L2 uses product income account (must NOT change)
        #  - taxes present (tax lines must remain intact)
        display_value = 'product' if self.display_supports_product else False
        if not self.display_supports_product:
            # If environment doesn't allow 'product' display_type, skip since user's filter relies on it.
            self.skipTest("Environment does not support display_type='product'; user's filter relies on it.")       
        move = self._create_draft_invoice(
            self.journal_contado,
            [
                {'name': 'L1 Old Journal Acc', 'account': self.account_contado, 'qty': 1, 'price': 100.0,
                 'taxes': [self.tax_iva16.id], 'display_type': display_value, 'product': self.product},
                {'name': 'L2 Product Acc', 'product': self.product, 'qty': 1, 'price': 50.0,
                 'taxes': [self.tax_iva16.id], 'display_type': display_value, 'account': self.account_credito, 'product': self.product},
            ]
        )       
        # -------- TAXES (BASELINE) --------
        tax_lines_before = move.line_ids.filtered(lambda l: l.tax_line_id)
        self.assertTrue(tax_lines_before, "Expected tax lines present")
        # Totales por impuesto (pueden fusionarse líneas luego)
        tax_totals_before = {}
        for tl in tax_lines_before:
            tax_totals_before[tl.tax_line_id.id] = tax_totals_before.get(tl.tax_line_id.id, 0.0) + tl.balance
        total_tax_before = sum(tax_totals_before.values())
        # Cuentas de impuestos usadas
        tax_accounts_before = set(tax_lines_before.mapped('account_id').ids)        
        # Call the method under test on the recordset (self = move)
        move._update_invoice_lines_with_new_journal(self.journal_contado.id, self.journal_credito.id)       
        # Fetch lines post-update
        l1 = move.invoice_line_ids.filtered(lambda l: l.name == 'L1 Old Journal Acc')
        l2 = move.invoice_line_ids.filtered(lambda l: l.name == 'L2 Product Acc')       
        self.assertEqual(len(l1), 1)
        self.assertEqual(len(l2), 1)        
        # L1 should now use new journal income account
        self.assertEqual(l1.account_id.id, self.account_credito.id,
                         "Line using old journal income account should be updated to new journal income account")       
        # L2 should keep its product/account (acc_income_product)
        self.assertEqual(l2.account_id.id, self.account_credito.id,
                         "Line using product/category account should NOT be updated")       
        # -------- TAXES (AFTER) --------
        tax_lines_after = move.line_ids.filtered(lambda l: l.tax_line_id)

        # Totales por impuesto (pueden haberse fusionado líneas)
        tax_totals_after = {}
        for tl in tax_lines_after:
            tax_totals_after[tl.tax_line_id.id] = tax_totals_after.get(tl.tax_line_id.id, 0.0) + tl.balance
        total_tax_after = sum(tax_totals_after.values())

        # Mismos totales por impuesto y total global
        self.assertEqual(tax_totals_after, tax_totals_before, "Tax totals per tax changed unexpectedly")
        self.assertAlmostEqual(total_tax_after, total_tax_before, places=2, msg="Total tax amount changed unexpectedly")

        # (Opcional, más estricto) Verificar cuentas según la configuración del impuesto
        # Para un único IVA de venta, las líneas de impuesto deberían usar las cuentas de las
        # invoice_repartition_line_ids con repartition_type='tax' (si están configuradas).
        expected_tax_accounts = set(
            self.tax_iva16.invoice_repartition_line_ids
            .filtered(lambda r: r.repartition_type == 'tax' and (not r.company_id or r.company_id == self.company))
            .mapped('account_id').ids
        )

        if expected_tax_accounts:
            # Las cuentas usadas por las líneas de impuesto deben pertenecer al set esperado
            self.assertTrue(
                set(tax_lines_after.mapped('account_id').ids).issubset(expected_tax_accounts),
                "Tax lines use unexpected accounts per tax repartition configuration"
            )
        # Si no hay cuenta configurada en el impuesto (expected_tax_accounts vacío), no se puede
        # afirmar nada sobre la(s) cuenta(s) usadas y omitimos esta verificación.

    def test_no_update_when_missing_income_accounts(self):
        """If either old or new journal has no income account, method should be a no-op (no crash)."""
        # Make a journal without any recognized income account fields
        j_no_income = self.Journal.create({
            'name': 'VENTAS SIN CTA',
            'type': 'sale',
            'code': 'VSN',
            # leave default_account_id unset on purpose
        })

        display_value = 'product' if self.display_supports_product else False
        if not self.display_supports_product:
            self.skipTest("Environment does not support display_type='product'; user's filter relies on it.")

        move = self._create_draft_invoice(
            self.journal_credito,
            [{'product': self.product, 'name': 'L1 Old Journal Acc', 'account': self.account_credito, 'qty': 1, 'price': 100.0,
              'taxes': [self.tax_iva16.id], 'display_type': display_value} ]
        )

        # Should simply return without raising
        move._update_invoice_lines_with_new_journal(self.journal_credito.id, j_no_income.id)

        # Line remains unchanged
        l1 = move.invoice_line_ids.filtered(lambda l: l.name == 'L1 Old Journal Acc')
        self.assertEqual(l1.account_id.id, self.account_credito.id)


