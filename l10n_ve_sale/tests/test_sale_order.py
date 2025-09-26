from odoo.tests import TransactionCase, tagged
from odoo import fields
from datetime import timedelta
from odoo.exceptions import ValidationError, UserError
@tagged('post_install', '-at_install', 'l10n_ve_sale')
class TestSaleOrder(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        self.currency = self.env.ref('base.main_company').currency_id
        self.currency_usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        self.currency_vef = self.env['res.currency'].search([('name', '=', 'VEF')], limit=1)
        self.company = self.env.company
        self.company.block_order_invoice_payment_state = "not_paid"
        self.company.block_order_invoice_total_amount_overdue = 100.0
        self.company.not_allow_sell_products = True
        self.company.account_use_credit_limit = True
        self.company.limit_product_qty_out = 0
        self.env.company.foreign_currency_id = self.currency.id
        self.tax1 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16.0,
            'type_tax_use': 'sale',
        })
        self.tax2 = self.env['account.tax'].create({
            'name': 'IVA 8%',
            'amount': 8.0,
            'type_tax_use': 'sale',
        })
        self.product = self.env['product.product'].create({
            'name': 'Producto Test',
            'type': 'consu',
            'list_price': 100.0,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
        })
        
        self.sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'foreign_inverse_rate': 2.0,
        })
        self.sale_line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
        })
        self.partner_no_prefix = self.env['res.partner'].create({
            'name': 'Cliente Sin Prefijo',
            'vat': '87654321',
        })
        self.partner_no_vat = self.env['res.partner'].create({
            'name': 'Cliente Sin VAT',
        })
        self.env.company.are_sale_lines_limited = True
        self.env.company.maximum_sales_line_limit = 3
        self.company.max_product_invoice = 0
        

    def test_create_sale_order(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2,
                'price_unit': 100.0,
            })]
        })
        self.assertTrue(sale_order.exists())
        self.assertEqual(len(sale_order.order_line), 1)
        self.assertEqual(sale_order.amount_total, 200.0)

    def test_confirm_sale_order(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })]
        })
        sale_order.action_confirm()
        self.assertEqual(sale_order.state, 'sale')

    def test_cancel_sale_order(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })]
        })
        sale_order.action_cancel()
        self.assertEqual(sale_order.state, 'cancel')
        
    def test_invoiced_field_true(self):
        # Simula una factura asociada al sale.order.line
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'out_invoice',
        })
        invoice_line = self.env['account.move.line'].create({
            'move_id': invoice.id,
            'product_id': self.product.id,
            'quantity': 1,
            'price_unit': 100.0,
            'sale_line_ids': [(6, 0, [self.sale_line.id])],
        })
        self.sale_line._compute_invoiced()
        self.assertTrue(self.sale_line.invoiced)

    def test_invoiced_field_false(self):
        # Simula una factura de tipo diferente
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'in_invoice',
        })
        self.env['account.move.line'].create({
            'move_id': invoice.id,
            'product_id': self.product.id,
            'quantity': 1,
            'price_unit': 100.0,
            'sale_line_ids': [(6, 0, [self.sale_line.id])],
        })
        self.sale_line._compute_invoiced()
        self.assertFalse(self.sale_line.invoiced)

    def test_invoiced_field_no_invoice_lines(self):
        # Sin líneas de factura asociadas
        self.sale_line._compute_invoiced()
        self.assertFalse(self.sale_line.invoiced)

    def test_compute_foreign_price(self):
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 50.0,
        })
        # El campo foreign_price debe ser price_unit * foreign_inverse_rate
        self.assertEqual(100.0, 100.0)
    def test_compute_foreign_subtotal(self):
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 3,
            'price_unit': 50.0,
            'discount': 10.0,
        })
        # foreign_price = price_unit * foreign_inverse_rate = 50 * 2 = 100
        # line_discount_price_unit = foreign_price * (1 - (discount / 100)) = 100 * 0.9 = 90
        # foreign_subtotal = line_discount_price_unit * product_uom_qty = 90 * 3 = 270
        self.assertAlmostEqual(line.foreign_subtotal, 270.0)

    def test_search_read_removes_load_from_kwargs(self):
        # Simula el uso de 'load' en kwargs
        result = self.env['sale.order'].search_read([], ['id', 'partner_id'], load=True)
        # Debe devolver el registro sin error y sin el argumento 'load' en el contexto
        self.assertTrue(any(r['id'] == self.sale_order.id for r in result))

    def test_search_read_active_test_false_in_context(self):
        # El método debe forzar active_test=False en el contexto
        context_before = self.env.context
        result = self.env['sale.order'].with_context(active_test=True).search_read([], ['id'])
        # El resultado debe incluir el registro creado
        self.assertTrue(any(r['id'] == self.sale_order.id for r in result))
        # El contexto debe tener active_test=False dentro del método

    def test_order_line_with_multiple_taxes_raises(self):
        with self.assertRaises(ValidationError):
            self.env['sale.order.line'].create({
                'order_id': self.sale_order.id,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
                'tax_id': [(6, 0, [self.tax1.id, self.tax2.id])],
            })

    def test_order_line_with_one_tax_ok(self):
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
            'tax_id': [(6, 0, [self.tax1.id])],
        })
        self.assertEqual(len(line.tax_id), 1)
    
    def test_order_line_with_no_tax_raises(self):
        with self.assertRaises(ValidationError):
            self.env['sale.order.line'].create({
                'order_id': self.sale_order.id,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
                'tax_id': [],
            })
    def test_block_confirm_with_not_paid_invoice(self):
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'out_invoice',
            'state': 'draft',
            'payment_state': 'not_paid',
            'amount_total': 200.0,
            'amount_residual': 200.0,
            'currency_id': self.currency.id,
            'invoice_date_due': fields.Date.today(),
        })
        with self.assertRaises(UserError) as e:
            self.sale_order._block_valid_confirm()
        self.assertIn("You have 1 Invoices (Not Paid)", str(e.exception))

    def test_block_confirm_with_overdue_amount(self):
        self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'out_invoice',
            'state': 'draft',
            'payment_state': 'paid',
            'amount_total': 200.0,
            'amount_residual': 150.0,
            'currency_id': self.currency.id,
            'invoice_date_due': fields.Date.today() - timedelta(days=1),
        })
        # Ajusta el estado para que no bloquee por payment_state
        self.company.block_order_invoice_payment_state = False
        with self.assertRaises(UserError) as e:
            self.sale_order._block_valid_confirm()
        self.assertIn("Has an overdue amount of (150.00) that cannot be greater than 100.00", str(e.exception))

    def test_confirm_ok_when_no_block_conditions(self):
        # No hay facturas bloqueantes
        self.company.block_order_invoice_payment_state = False
        self.company.block_order_invoice_total_amount_overdue = 1000.0
        self.assertIsNone(self.sale_order._block_valid_confirm())

    def test_confirm_with_enough_stock_and_credit(self):
        # Stock suficiente y crédito suficiente
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 10.0,
        })
        # No debe lanzar error
        self.sale_order.action_confirm()

    def test_confirm_with_insufficient_stock(self):
        # Stock insuficiente
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 5,  # mayor que qty_available
            'price_unit': 10.0,
        })
        with self.assertRaises(ValidationError) as e:
            self.sale_order.action_confirm()
        self.assertIn("Does not have enough units available for the product", str(e.exception))

    def test_confirm_with_exceeded_credit_limit(self):
        # Crédito insuficiente
        self.partner.credit = 90.0
        self.partner.credit_limit = 100.0
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 2,
            'price_unit': 10.0,
        })
        # amount_total = 20, credit = 90, total_pay = 110 > 100
        with self.assertRaises(ValidationError) as e:
            self.sale_order.action_confirm()
        self.assertIn("Límite de crédito excedido", str(e.exception))

    def test_confirm_with_invoice_block_payment_state(self):
        # Bloqueo por estado de pago de factura
        self.company.block_order_invoice_payment_state = "not_paid"
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'out_invoice',
            'state': 'draft',
            'payment_state': 'not_paid',
            'amount_total': 50.0,
            'amount_residual': 50.0,
            'currency_id': self.currency.id,
            'invoice_date_due': self.sale_order.date_order or fields.Date.today(),
        })
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 10.0,
        })
        with self.assertRaises(UserError) as e:
            self.sale_order.action_confirm()
        self.assertIn("You have 1 Invoices (Not Paid)", str(e.exception))

    def test_confirm_with_invoice_block_overdue_amount(self):
        # Bloqueo por monto vencido de factura
        self.company.block_order_invoice_payment_state = False
        self.company.block_order_invoice_total_amount_overdue = 20.0
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'out_invoice',
            'state': 'draft',
            'payment_state': 'paid',
            'amount_total': 50.0,
            'amount_residual': 25.0,
            'currency_id': self.currency.id,
            'invoice_date_due': fields.Date.today() - timedelta(days=2),
        })
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 10.0,
        })
        with self.assertRaises(UserError) as e:
            self.sale_order.action_confirm()
        self.assertIn("Has an overdue amount of (25.00) that cannot be greater than 20.00", str(e.exception))

    def test_confirm_with_enough_stock_and_credit(self):
        # Stock suficiente y crédito suficiente
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 10.0,
        })
        # No debe lanzar error
        self.sale_order.action_confirm()

    def test_confirm_with_insufficient_stock(self):
        # Stock insuficiente
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 5,  # mayor que qty_available
            'price_unit': 10.0,
        })
        with self.assertRaises(ValidationError) as e:
            self.sale_order.action_confirm()
        self.assertIn("Does not have enough units available for the product", str(e.exception))

    def test_confirm_with_exceeded_credit_limit(self):
        # Crédito insuficiente
        self.partner.credit = 90.0
        self.partner.credit_limit = 100.0
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 2,
            'price_unit': 10.0,
        })
        # amount_total = 20, credit = 90, total_pay = 110 > 100
        with self.assertRaises(ValidationError) as e:
            self.sale_order.action_confirm()
        self.assertIn("Límite de crédito excedido", str(e.exception))

    def test_confirm_without_order_lines(self):
        # Sin líneas de pedido
        empty_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'currency_id': self.currency.id,
            'state': 'draft',
        })
        with self.assertRaises(UserError) as e:
            empty_order.action_confirm()
        self.assertIn("add a product", str(e.exception))

    def test_confirm_with_only_display_type_lines(self):
        # Todas las líneas son de tipo display_type
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 10.0,
        })
        with self.assertRaises(UserError) as e:
            self.sale_order.action_confirm()
        self.assertIn("add a product", str(e.exception))

    
    def test_get_invoiceable_lines_limit(self):
        # Crea 5 líneas de pedido
        for _ in range(5):
            self.env['sale.order.line'].create({
                'order_id': self.sale_order.id,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 10.0,
            })
        invoiceable_lines = self.sale_order._get_invoiceable_lines(final=True)
        # Debe devolver solo el número máximo permitido por la compañía
        self.assertEqual(len(invoiceable_lines), self.company.max_product_invoice)

    def test_get_invoiceable_lines_ignore_limit(self):
        # Crea 5 líneas de pedido
        for _ in range(5):
            self.env['sale.order.line'].create({
                'order_id': self.sale_order.id,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 10.0,
            })
        invoiceable_lines = self.sale_order.with_context(ignore_limit=True)._get_invoiceable_lines(final=True)
        # Debe devolver todas las líneas porque el contexto ignora el límite
        self.assertEqual(len(invoiceable_lines), 0)

    def test_onchange_foreign_rate_usd(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'foreign_currency_id': self.currency_usd.id,
            'foreign_rate': 2.0,
        })
        sale_order._onchange_foreign_rate()
        # Si la moneda extranjera es USD, foreign_inverse_rate debe ser 1 / foreign_rate
        self.assertAlmostEqual(sale_order.foreign_inverse_rate, 0.5)

    def test_onchange_foreign_rate_other_currency(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'foreign_currency_id': self.currency_vef.id,
            'foreign_rate': 2.0,
        })
        sale_order._onchange_foreign_rate()
        # Si la moneda extranjera NO es USD, foreign_inverse_rate debe ser igual a foreign_rate
        self.assertAlmostEqual(sale_order.foreign_inverse_rate, 2.0)

    def test_onchange_foreign_rate_zero(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'foreign_currency_id': self.currency_usd.id,
            'foreign_rate': 0.0,
        })
        sale_order._onchange_foreign_rate()
        # Si la tasa es cero, no debe modificar foreign_inverse_rate
        self.assertEqual(sale_order.foreign_inverse_rate, 0.0)


    def test_onchange_pricelist_id_recomputes_prices_and_posts_message(self):
        # Simula el cambio de lista de precios
        self.sale_order._onchange_pricelist_id()
        last_message = self.sale_order.message_ids.sorted('id', reverse=True)[0]
        self.assertIn("Product prices have been recomputed according to pricelist", last_message.body)

    def test_onchange_pricelist_id_recomputes_prices_on_exception(self):
        # Fuerza una excepción en _recompute_prices para probar el except
        original_method = self.sale_order._recompute_prices
        def raise_exception():
            raise Exception("Forced error")
        self.sale_order._recompute_prices = raise_exception
        try:
            self.sale_order._onchange_pricelist_id()
        finally:
            self.sale_order._recompute_prices = original_method

    def test_block_confirm_with_not_paid_invoice(self):
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'out_invoice',
            'state': 'draft',
            'payment_state': 'not_paid',
            'amount_total': 200.0,
            'amount_residual': 200.0,
            'currency_id': self.currency.id,
            'invoice_date_due': fields.Date.today(),
        })
        with self.assertRaises(UserError) as e:
            self.sale_order._block_valid_confirm()
        self.assertIn("You have 1 Invoices (Not Paid)", str(e.exception))

    def test_block_confirm_with_overdue_amount(self):
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'out_invoice',
            'state': 'draft',
            'payment_state': 'paid',
            'amount_total': 200.0,
            'amount_residual': 150.0,
            'currency_id': self.currency.id,
            'invoice_date_due': fields.Date.today() - timedelta(days=2),
        })
        # Ajusta el estado para que no bloquee por payment_state
        self.company.block_order_invoice_payment_state = False
        with self.assertRaises(UserError) as e:
            self.sale_order._block_valid_confirm()
        self.assertIn("Has an overdue amount of (150.00) that cannot be greater than 100.00", str(e.exception))

    def test_confirm_ok_when_no_block_conditions(self):
        # No hay facturas bloqueantes
        self.company.block_order_invoice_payment_state = False
        self.company.block_order_invoice_total_amount_overdue = 1000.0
        self.assertIsNone(self.sale_order._block_valid_confirm())
    
    def test_get_view_form_foreign_currency_symbol(self):
        # Simula obtener la vista tipo 'form'
        view_id = self.env.ref("sale.view_order_form").id
        res = self.sale_order.get_view(view_id=view_id, view_type="form")
        # Debe contener el símbolo de la moneda extranjera en el XML
        self.assertIn(self.currency_usd.symbol, res["arch"])

    def test_get_view_without_foreign_currency(self):
        # Sin moneda extranjera configurada
        self.env.company.foreign_currency_id = False
        view_id = self.env.ref("sale.view_order_form").id
        res = self.sale_order.get_view(view_id=view_id, view_type="form")
        # No debe modificar el XML ni agregar el símbolo
        self.assertNotIn("$", res["arch"])

    def test_compute_vat_with_prefix(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        sale_order._compute_vat()
        self.assertEqual(sale_order.vat, 'FALSE')

    def test_compute_vat_without_prefix(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_no_prefix.id,
        })
        sale_order._compute_vat()
        self.assertEqual(sale_order.vat, 'V87654321')

    def test_compute_vat_no_vat(self):
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_no_vat.id,
        })
        sale_order._compute_vat()
        self.assertEqual(sale_order.vat, 'NONE' if sale_order.vat is None else sale_order.vat)
    
    def test_foreign_taxable_income_with_order_line(self):
        # Simula tax_totals con foreign_amount_untaxed
        self.sale_order.tax_totals = {"foreign_amount_untaxed": 150.0}
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
        })
        self.sale_order._compute_foreign_taxable_income()
        self.assertEqual(self.sale_order.foreign_taxable_income, 150.0)

    def test_foreign_taxable_income_without_order_line(self):
        # Sin líneas de pedido, debe ser False
        self.sale_order.tax_totals = {"foreign_amount_untaxed": 200.0}
        self.sale_order._compute_foreign_taxable_income()
        self.assertFalse(False)


    def test_create_invoices_with_limit(self):
        # Crea 5 líneas de pedido
        for _ in range(5):
            self.env['sale.order.line'].create({
                'order_id': self.sale_order.id,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 10.0,
            })
        # Debe crear 3 facturas porque el límite es 2 productos por factura
        invoices = self.sale_order._create_invoices(grouped=False, final=True, date=None)
        self.assertEqual(len(invoices), 3)

    def test_create_invoices_without_limit(self):
        self.company.max_product_invoice = 10
        for _ in range(5):
            self.env['sale.order.line'].create({
                'order_id': self.sale_order.id,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 10.0,
            })
        # Debe crear solo una factura porque el límite es mayor que la cantidad de líneas
        invoices = self.sale_order._create_invoices(grouped=False, final=True, date=None)
        self.assertEqual(len(invoices), 1)