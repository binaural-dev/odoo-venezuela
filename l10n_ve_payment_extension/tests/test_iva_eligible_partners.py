import logging
from odoo.tests import tagged, TransactionCase, Form
from odoo import Command, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "iva_eligible_partners")
class TestIvaEligiblePartners(TransactionCase):
    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")

        iva_seq = self.env["ir.sequence"].create({
            "name": "IVA Retention Seq",
            "code": "payment.retention.iva",
            "prefix": "",
            "padding": 8,
            "number_next_actual": 2,
        })
        inv_seq = self.env["ir.sequence"].create({
            "name": "Invoice Seq",
            "code": "account.move",
            "prefix": "INV/",
            "padding": 8,
            "number_next_actual": 2,
        })
        refund_seq = self.env["ir.sequence"].create({
            "name": "Credit Note Seq",
            "code": "",
            "prefix": "NC/",
            "padding": 8,
            "number_next_actual": 2,
        })

        bank_account = self.env["account.account"].search(
            [("account_type", "=", "liquidity")], limit=1
        )
        transitory_account = self.env["account.account"].search(
            [("account_type", "=", "other")], limit=1
        )
        profit_account = self.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        loss_account = self.env["account.account"].search(
            [("account_type", "=", "expense")], limit=1
        )

        self.iva_supplier_journal = self.env["account.journal"].create({
            "name": "Ret IVA Proveedor",
            "code": "RIVAP",
            "type": "bank",
            "sequence_id": iva_seq.id,
            "company_id": self.env.company.id,
            "bank_account_id": bank_account.id,
            "default_account_id": transitory_account.id,
            "profit_account_id": profit_account.id,
            "loss_account_id": loss_account.id,
        })

        self.iva_customer_journal = self.env["account.journal"].create({
            "name": "Ret IVA Cliente",
            "code": "RIVAC",
            "type": "bank",
            "sequence_id": iva_seq.id,
            "company_id": self.env.company.id,
            "bank_account_id": bank_account.id,
            "default_account_id": transitory_account.id,
            "profit_account_id": profit_account.id,
            "loss_account_id": loss_account.id,
        })

        self.purchase_journal = self.env["account.journal"].create({
            "name": "Compras",
            "code": "COMP",
            "type": "purchase",
            "sequence_id": inv_seq.id,
            "refund_sequence_id": refund_seq.id,
            "company_id": self.env.company.id,
        })

        self.sale_journal = self.env["account.journal"].create({
            "name": "Ventas",
            "code": "VENT",
            "type": "sale",
            "sequence_id": inv_seq.id,
            "refund_sequence_id": refund_seq.id,
            "company_id": self.env.company.id,
        })

        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
            "iva_supplier_retention_journal_id": self.iva_supplier_journal.id,
            "iva_customer_retention_journal_id": self.iva_customer_journal.id,
        })

        payment_in = self.env.ref("account.account_payment_method_manual_in")
        payment_out = self.env.ref("account.account_payment_method_manual_out")
        self.iva_supplier_journal.write({
            "inbound_payment_method_line_ids": [Command.create({
                "payment_method_id": payment_in.id, "name": "Manual",
            })],
            "outbound_payment_method_line_ids": [Command.create({
                "payment_method_id": payment_out.id, "name": "Manual",
            })],
        })
        self.iva_customer_journal.write({
            "inbound_payment_method_line_ids": [Command.create({
                "payment_method_id": payment_in.id, "name": "Manual",
            })],
            "outbound_payment_method_line_ids": [Command.create({
                "payment_method_id": payment_out.id, "name": "Manual",
            })],
        })

        self.tax_group_iva = self.env["account.tax.group"].create({"name": "IVA 16%"})

        self.tax_purchase = self.env["account.tax"].create({
            "name": "IVA Compra 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "tax_group_id": self.tax_group_iva.id,
        })
        self.tax_sale = self.env["account.tax"].create({
            "name": "IVA Venta 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "tax_group_id": self.tax_group_iva.id,
        })

        income_account = self.env["account.account"].browse(24)
        expense_account = self.env["account.account"].browse(30)

        self.product = self.env["product.product"].create({
            "name": "Producto Prueba",
            "type": "service",
            "list_price": 100,
            "barcode": "123456789",
            "purchase_ok": True,
            "sale_ok": True,
            "supplier_taxes_id": [(6, 0, [self.tax_purchase.id])],
            "taxes_id": [(6, 0, [self.tax_sale.id])],
            "property_account_income_id": income_account.id,
            "property_account_expense_id": expense_account.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "Test Partner",
            "customer_rank": 1,
            "withholding_type_id": self.env["account.withholding.type"]
            .search([("name", "=", "75%")], limit=1)
            .id,
        })

    def _create_invoice(self, move_type, tax, journal, force_posted=True):
        invoice = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 2,
                    "price_unit": 100,
                    "tax_ids": [(6, 0, [tax.id])],
                    "price_subtotal": 200,
                    "price_total": 232,
                    "foreign_rate": 2.0,
                    "foreign_price": 200,
                    "foreign_subtotal": 400,
                    "foreign_price_total": 464,
                }),
            ],
        })
        try:
            invoice.action_post()
        except Exception:
            pass
        if force_posted and invoice.state != "posted":
            self.env.cr.execute(
                "UPDATE account_move SET state = 'posted' WHERE id = %s",
                [invoice.id],
            )
            invoice.invalidate_recordset()
        return invoice

    def _force_amount_residual(self, invoice, value):
        self.env.cr.execute(
            "UPDATE account_move SET amount_residual = %s, amount_residual_signed = %s WHERE id = %s",
            [value, value, invoice.id],
        )
        invoice.invalidate_recordset()

    def _get_iva_eligible_partners(self, retention_type, move_type):
        retention = self.env["account.retention"].create({
            "type_retention": retention_type,
            "type": move_type,
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        return retention.iva_eligible_partner_ids

    # ---- Supplier side ----

    def test_supplier_positive_invoice_is_eligible(self):
        invoice = self._create_invoice("in_invoice", self.tax_purchase, self.purchase_journal)
        self.assertGreater(invoice.amount_residual, 0)
        eligible = self._get_iva_eligible_partners("iva", "in_invoice")
        self.assertIn(self.partner, eligible)

    def test_supplier_zero_residual_not_eligible(self):
        invoice = self._create_invoice("in_invoice", self.tax_purchase, self.purchase_journal)
        self._force_amount_residual(invoice, 0.0)
        eligible = self._get_iva_eligible_partners("iva", "in_invoice")
        self.assertNotIn(self.partner, eligible)

    def test_supplier_negative_residual_not_eligible(self):
        invoice = self._create_invoice("in_invoice", self.tax_purchase, self.purchase_journal)
        self._force_amount_residual(invoice, -100.0)
        eligible = self._get_iva_eligible_partners("iva", "in_invoice")
        self.assertNotIn(self.partner, eligible)

    def test_supplier_select_eligible_loads_lines(self):
        self._create_invoice("in_invoice", self.tax_purchase, self.purchase_journal)
        with Form(self.env["account.retention"].with_context(
            default_type_retention="iva", default_type="in_invoice"
        )) as f:
            f.partner_id = self.partner
            f.date_accounting = fields.Date.today()
        retention = f.save()
        self.assertTrue(retention.retention_line_ids)

    def test_supplier_select_non_eligible_raises_error(self):
        invoice = self._create_invoice("in_invoice", self.tax_purchase, self.purchase_journal)
        self._force_amount_residual(invoice, 0.0)
        with self.assertRaises(UserError):
            with Form(self.env["account.retention"].with_context(
                default_type_retention="iva", default_type="in_invoice"
            )) as f:
                f.partner_id = self.partner
                f.date_accounting = fields.Date.today()

    # ---- Customer side ----

    def test_customer_positive_invoice_is_eligible(self):
        invoice = self._create_invoice("out_invoice", self.tax_sale, self.sale_journal)
        self.assertGreater(invoice.amount_residual, 0)
        eligible = self._get_iva_eligible_partners("iva", "out_invoice")
        self.assertIn(self.partner, eligible)

    def test_customer_zero_residual_not_eligible(self):
        invoice = self._create_invoice("out_invoice", self.tax_sale, self.sale_journal)
        self._force_amount_residual(invoice, 0.0)
        eligible = self._get_iva_eligible_partners("iva", "out_invoice")
        self.assertNotIn(self.partner, eligible)

    def test_customer_negative_residual_not_eligible(self):
        invoice = self._create_invoice("out_invoice", self.tax_sale, self.sale_journal)
        self._force_amount_residual(invoice, -100.0)
        eligible = self._get_iva_eligible_partners("iva", "out_invoice")
        self.assertNotIn(self.partner, eligible)

    # NOTE: Customer side onchange (select eligible → load lines) is not tested here
