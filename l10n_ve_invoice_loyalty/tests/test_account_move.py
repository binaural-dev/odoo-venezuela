import logging
import datetime
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError
from typing import Callable, Any
import functools

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_invoice_loyalty")
class TestAccountMove(TransactionCase):
    """Tests for invoice posting behaviour regarding the invoice date."""

    def setUp(self):
        super(TestAccountMove, self).setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
            }
        )



        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
        })
        
        self.partner_a = self.env['res.partner'].create({
            'name': 'Test Partner A',
            'customer_rank': 1,
        })
        
        self.company_data = {
            'company': self.env['res.company'].create({
                'name': 'Test Company',
                'currency_id': self.env.ref('base.VEF').id,
            }),
        }
        sequence = self.env['ir.sequence'].create({
            'name': 'Secuencia Factura',
            'code': 'account.move',
            'prefix': 'INV/',
            'padding': 8,
            "number_next_actual": 2,
        })
        refund_sequence = self.env['ir.sequence'].create({
            'name': 'nota de credito',
            'code': '',
            'prefix': 'NC/',
            'padding': 8,
            "number_next_actual": 2,
        })

        self.journal = self.env['account.journal'].create({
            'name': 'Diario de Ventas',
            'code': 'VEN',
            'type': 'sale',
            'sequence_id': sequence.id,
            "refund_sequence_id": refund_sequence.id,
            'company_id': self.env.company.id,
        })

    def _create_loyalty_reward_for_product(self, product):
        """Crea una loyalty.reward mínima para el producto dado, resolviendo selection fields de forma segura."""
        if 'loyalty.reward' not in self.env:
            self.skipTest("El modelo loyalty.reward no está disponible en este entorno de pruebas.")

        Reward = self.env['loyalty.reward']
        vals = {'discount_line_product_id': product.id}

        if 'name' in Reward._fields:
            vals['name'] = 'Test Reward'

        try:
            reward_type_sel = Reward.fields_get(['reward_type']).get('reward_type', {}).get('selection', [])
        except Exception:
            reward_type_sel = []
        if reward_type_sel:
            codes = [c for c, _ in reward_type_sel]
            vals['reward_type'] = 'discount' if 'discount' in codes else codes[0]

        try:
            discount_mode_sel = Reward.fields_get(['discount_mode']).get('discount_mode', {}).get('selection', [])
        except Exception:
            discount_mode_sel = []
        if discount_mode_sel:
            codes = [c for c, _ in discount_mode_sel]
            vals['discount_mode'] = 'fixed' if 'fixed' in codes else codes[0]

        if 'discount' in Reward._fields:
            vals['discount'] = 10.0

        if 'program_id' in Reward._fields and 'loyalty.program' in self.env:
            Program = self.env['loyalty.program']
            pvals = {}
            if 'name' in Program._fields:
                pvals['name'] = 'Test Program'

            try:
                pt_sel = Program.fields_get(['program_type']).get('program_type', {}).get('selection', [])
            except Exception:
                pt_sel = []
            if pt_sel:
                pvals['program_type'] = pt_sel[0][0]

            try:
                ap_sel = Program.fields_get(['applies_on']).get('applies_on', {}).get('selection', [])
            except Exception:
                ap_sel = []
            if ap_sel:
                pvals['applies_on'] = ap_sel[0][0]

            program = Program.create(pvals)
            vals['program_id'] = program.id

        return Reward.create(vals)
    
    def require_models(*required_modules: str) -> Callable:
        """
        Decorator for tests that checks if a set of models are installed.

        If any of the specified models are not installed, the test is failed
        with a message listing all the missing models. This is more efficient
        than checking one by one as it performs a single DB query.
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(self, *args: Any, **kwargs: Any) -> Any:
                missing_models = [
                    name for name in required_modules if name not in self.env
                ]
                
                if missing_models:
                    missing_list = ', '.join(sorted(missing_models))
                    self.fail(
                        f"Test error: The following models are not available in the environment: {missing_list}"
                    )
                    
                return func(self, *args, **kwargs)
            return wrapper
        return decorator


    def _create_invoice(
            self, 
            products, 
            move_type="out_invoice", 
            reversed_entry_id=None, 
            debit_origin_id=None, 
            ref = "Test Invoice",
            foreign_rate=38,
            foreign_inverse_rate=38,
            invoice_date=None
        ):
        """Helper function to create an invoice with given parameters.
        Args:
            products (list): List of dictionaries with product details.
            foreign_rate (float): Foreign exchange rate.
            foreign_inverse_rate (float): Inverse foreign exchange rate.
        """
        invoice_lines = [
            Command.create(
                {
                    "product_id": product["product_id"],
                    "quantity": product.get("quantity", 1),
                    "price_unit": product["price_unit"],
                    "tax_ids": product.get("tax_ids", []),
                }
            )
            for product in products
        ]

        name = self.journal.sequence_id.next_by_id()

        if move_type == "out_refund" and reversed_entry_id:
            name = self.journal.refund_sequence_id.next_by_id()

        if move_type == "out_invoice" and debit_origin_id:
            name = self.debit_journal.sequence_id.next_by_id()

        invoice_vals = {
            "name": name,
            "move_type": move_type,
            "partner_id": self.partner_a.id,
            "foreign_currency_id": self.currency_vef.id,
            "currency_id": self.currency_usd.id,
            "state": "draft",
            "foreign_rate": foreign_rate,
            "foreign_inverse_rate": foreign_inverse_rate,
            "manually_set_rate": True,
            "invoice_line_ids": invoice_lines,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "journal_id": self.journal.id,
            "correlative": 1,
        }

        # Solo para notas de crédito
        if move_type == "out_refund" and reversed_entry_id:
            invoice_vals["reversed_entry_id"] = reversed_entry_id.id
            invoice_vals["ref"] = ref

        if move_type == "out_invoice" and debit_origin_id:
            invoice_vals["debit_origin_id"] = debit_origin_id.id
            invoice_vals["ref"] = ref
        
        invoice = self.env["account.move"].create(invoice_vals)

        invoice.action_post()
        return invoice

    @require_models('sale.order')
    def test_zero_price_line_raises_validation_error(self):
        """A normal line with price_unit=0 should raise a ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_invoice(
                [
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 0.0,
                        "tax_ids": [(6, 0, [self.tax_iva16.id])],
                    }
                ]
            )
        _logger.info("test-> test_zero_price_line_raises_validation_error [OK].")

    @require_models('sale.order')
    def test_discount_product_allows_zero_price(self):
        """If company.sale_discount_product_id exists, it should allow price <= 0 for that product."""

        product_with_discount = self.env['product.product'].create({
            'name': 'Producto Cero Precio',
            'type': 'service',
            'list_price': 0,
            'barcode': '987654321',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
        })
        self.env.company.sale_discount_product_id = product_with_discount

        try:
            inv = self._create_invoice([
                {
                    "product_id": product_with_discount.id,  
                    "quantity": 1,
                    "price_unit": -8.0,                      
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                },
                {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 2.0,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                }
            ])
        except ValidationError as e:
            self.fail(f"ValidationError was raised but should not have been: {e}")

        self.assertTrue(inv, "Invoice was not created correctly.")
        self.assertTrue(any(
            line.product_id.id == product_with_discount.id and line.price_unit == -8.0
            for line in inv.invoice_line_ids
        ), "Discount line with price_unit=-8.0 not found")
        self.assertTrue(any(
            line.product_id.id == self.product.id and line.price_unit == 2.0
            for line in inv.invoice_line_ids
        ), "Normal line with price_unit=2.0 not found")

        _logger.info("test-> test_discount_product_allows_zero_price [OK].")


    @require_models('sale.order')
    def test_negative_price_line_raises_validation_error(self):
        """A normal line with price_unit < 0 should raise a ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_invoice([{
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": -0.01,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            }])
        
        _logger.info("test-> test_negative_price_line_raises_validation_error [OK].")

    @require_models('sale.order')
    def test_zero_price_other_product_still_raises(self):
        discount_prod = self.env['product.product'].create({
            'name': 'Prod Desc',
            'type': 'service',
            'list_price': 0,
        })
        self.env.company.sale_discount_product_id = discount_prod

        with self.assertRaises(ValidationError):
            self._create_invoice([{
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 0.0,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            }])
        
        _logger.info("test-> test_zero_price_other_product_still_raises [OK].")

    @require_models('sale.order')
    def test_out_refund_with_zero_price_on_normal_product_raises(self):
        inv = self._create_invoice([{
            "product_id": self.product.id,
            "quantity": 1,
            "price_unit": 10.0,
            "tax_ids": [(6, 0, [self.tax_iva16.id])],
        }], move_type="out_invoice")

        with self.assertRaises(ValidationError):
            self._create_invoice([{
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 0.0,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            }], move_type="out_refund", reversed_entry_id=inv, ref="Refund test")

        _logger.info("test-> test_out_refund_with_zero_price_on_normal_product_raises [OK].")

    @require_models('sale.order')
    def test_write_changing_price_to_zero_raises(self):
        self.env.company.sale_discount_product_id = False

        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "journal_id": self.journal.id,
            "correlative": 1,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 10.0,
            })],
        })

        line = move.invoice_line_ids[0]

        with self.assertRaises(ValidationError):
            move.write({
                "invoice_line_ids": [Command.update(line.id, {"price_unit": 0.0})]
            })
        _logger.info("test-> test_write_changing_price_to_zero_raises [OK].")

    @require_models('loyalty.reward')
    def test_loyalty_reward_allows_nonpositive_price(self):
        """If there is a loyalty.reward whose discount_line_product_id matches the product of the line,
        price_unit <= 0 should be allowed."""
        if 'sale_discount_product_id' in self.env.company._fields:
            self.env.company.sale_discount_product_id = False

        reward_product = self.env['product.product'].create({
            'name': 'Producto Recompensa',
            'type': 'service',
            'list_price': 0,
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
        })
        self._create_loyalty_reward_for_product(reward_product)

        try:
            inv = self._create_invoice([
                {"product_id": reward_product.id, "quantity": 1, "price_unit": -5.0,
                "tax_ids": [(6, 0, [self.tax_iva16.id])]},
                {"product_id": self.product.id, "quantity": 1, "price_unit": 3.0,
                "tax_ids": [(6, 0, [self.tax_iva16.id])]},
            ])
        except ValidationError as e:
            self.fail(f"ValidationError was raised with reward product and should not have been: {e}")

        self.assertTrue(inv, "Invoice was not created correctly.")
        self.assertTrue(any(
            l.product_id.id == reward_product.id and l.price_unit == -5.0
            for l in inv.invoice_line_ids
        ), "Reward line with price_unit=-5.0 not found")

        _logger.info("test-> test_loyalty_reward_allows_nonpositive_price [OK].")