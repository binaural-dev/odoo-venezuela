from datetime import date, datetime, timedelta
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", 'l10n_ve_fiscal_lock_days')
class TestFiscalLockDays(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.ref('base.main_company')
        self.company.tax_period = "fortnightly"
        self.company.lock_date_tax_validation = True
        self.company.tax_lock_date = date(2025, 8, 16)  # Change according to the last day of the fiscal period shown by the logger, set it ONE day ahead.
        self.company.country_id = self.env.ref('base.ve')
        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})
        self.journal = self.env['account.journal'].create({
            'name': 'Diario de Ventas',
            'code': 'VEN',
            'type': 'sale',
            'company_id': self.company.id,
        })
        self.tax_group_iva16 = self.env["account.tax.group"].create({"name": "IVA 16%"})
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': self.tax_group_iva16.id,
            'country_id': self.company.country_id.id,
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
            'company_id': self.company.id,
        })


        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")

        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "foreign_currency_id": self.currency_vef.id,  
            }
        )

        self.sale_order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})],
        })
        self.sale_order.action_confirm()  
        self.sale_order.write({'date_order': datetime(2025, 8, 1, 12, 0, 0)})  # Ensure the date is before the lock date




    def test_company_fields(self):
        self.company.tax_period = "monthly"
        self.assertEqual(self.company.tax_period, "monthly")
        self.company.lock_date_tax_validation = False
        self.assertFalse(self.company.lock_date_tax_validation)

    def test_invoice_blocked_by_lock_date(self):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'company_id': self.company.id,
        })
        with self.assertRaises(ValidationError):
            move._check_tax_lock_date()

    def test_invoice_allowed_when_lock_date_matches(self):
        # Set tax_lock_date to last day of previous fortnight
        today = date.today()
        last_day = today.replace(day=15) if today.day > 15 else (today.replace(day=1) - timedelta(days=1))
        self.company.tax_lock_date = last_day

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'company_id': self.company.id,
        })
        # Should not raise
        move._check_tax_lock_date()
    
    def test_lock_date_with_pending_sale_orders(self):
        wizard = self.env["account.change.lock.date"].create({
            "tax_lock_date": date.today() - timedelta(days=1),
        })
        with self.assertRaises(ValidationError):
            wizard.change_lock_date()