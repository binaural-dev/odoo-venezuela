from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "account_retention_recalculate_sync")
class TestAccountRetentionRecalculateSync(RetentionTestCommon):
    """
    Task #83486 gap: account.retention.action_recalculate() must SYNC the
    set of retention lines against the invoice's current lines (add/remove,
    not just update amounts of lines that already exist), scoped to the
    invoice(s) that triggered the recalculation. All scenarios below build
    the invoice with the standard Form helpers, which leave it in 'draft'
    - the same state the "Recalcular retenciones" button requires.
    """

    def setUp(self):
        super().setUp()
        # A second real IVA rate (8%), needed to test adding/removing an
        # aliquot - the shared fixtures only define a 16% tax.
        self.tax_iva_8_purchase = self.env["account.tax"].create({
            "name": "IVA 8% Compras",
            "amount_type": "percent",
            "amount": 8.0,
            "type_tax_use": "purchase",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group_iva.id,
            "country_id": self.company.country_id.id,
        })
        self.product_iva_8 = self.env["product.product"].create({
            "name": "Servicio 8%",
            "list_price": 100,
            "property_account_income_id": self.acc_income.id,
            "taxes_id": [(6, 0, [self.tax_iva_8_purchase.id])],
            "supplier_taxes_id": [(6, 0, [self.tax_iva_8_purchase.id])],
        })

    def _create_two_rate_iva_invoice(self):
        """Draft supplier invoice with one 16% line and one 8% line."""
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        # add the second (8%) line directly on the draft invoice
        self.env["account.move.line"].create({
            "move_id": invoice.id,
            "product_id": self.product_iva_8.id,
            "quantity": 1,
            "price_unit": 100,
            "tax_ids": [Command.set(self.product_iva_8.supplier_taxes_id.ids)],
            "name": self.product_iva_8.name,
        })
        return invoice

    def _make_iva_retention_for(self, invoice):
        today = fields.Date.today()
        lines_data = self.env["account.retention"].compute_retention_lines_data(invoice)
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": today, "date_accounting": today,
            "retention_line_ids": [Command.create(data) for data in lines_data],
        })
        retention.action_post()
        return retention

    def _make_islr_retention_for(self, invoice):
        today = fields.Date.today()
        payment_concepts = invoice._get_payment_concepts_from_invoice()
        line_cmds = [
            Command.create({
                "move_id": invoice.id,
                "payment_concept_id": concept_id,
                "invoice_type": invoice.move_type,
                "invoice_amount": base_amount,
            })
            for concept_id, base_amount, _invoice_line_id in payment_concepts
        ]
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": today, "date_accounting": today,
            "retention_line_ids": line_cmds,
        })
        retention.action_post()
        return retention

    def test_01_remove_iva_aliquot_deletes_line_and_logs_note(self):
        invoice = self._create_two_rate_iva_invoice()
        retention = self._make_iva_retention_for(invoice)
        self.assertEqual(len(retention.retention_line_ids), 2)

        line_8 = retention.retention_line_ids.filtered(
            lambda l: round(l.aliquot, 2) == 8.0
        )
        self.assertTrue(line_8)

        messages_before = len(retention.message_ids)
        invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_iva_8
        ).unlink()

        retention.action_recalculate(moves=invoice)

        self.assertEqual(len(retention.retention_line_ids), 1)
        self.assertFalse(
            retention.retention_line_ids.filtered(lambda l: round(l.aliquot, 2) == 8.0)
        )
        self.assertGreater(len(retention.message_ids), messages_before)
        _logger.info("========= test_01 passed =========")

    def test_02_add_new_iva_aliquot_creates_line(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        retention = self._make_iva_retention_for(invoice)
        self.assertEqual(len(retention.retention_line_ids), 1)

        self.env["account.move.line"].create({
            "move_id": invoice.id,
            "product_id": self.product_iva_8.id,
            "quantity": 1,
            "price_unit": 100,
            "tax_ids": [Command.set(self.product_iva_8.supplier_taxes_id.ids)],
            "name": self.product_iva_8.name,
        })

        retention.action_recalculate(moves=invoice)

        self.assertEqual(len(retention.retention_line_ids), 2)
        self.assertTrue(
            retention.retention_line_ids.filtered(lambda l: round(l.aliquot, 2) == 8.0)
        )
        _logger.info("========= test_02 passed =========")

    def test_03_add_new_islr_concept_creates_line(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        retention = self._make_islr_retention_for(invoice)
        self.assertEqual(len(retention.retention_line_ids), 1)

        self.env["account.move.line"].create({
            "move_id": invoice.id,
            "product_id": self.product_islr_three.id,
            "quantity": 1,
            "price_unit": 100,
            "name": self.product_islr_three.name,
        })

        retention.action_recalculate(moves=invoice)

        self.assertEqual(len(retention.retention_line_ids), 2)
        self.assertTrue(
            retention.retention_line_ids.filtered(
                lambda l: l.payment_concept_id == self.concept_three
            )
        )
        _logger.info("========= test_03 passed =========")

    def test_04_remove_one_of_two_islr_lines_same_concept_keeps_one(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        # second product also under concept_one, so the invoice has two
        # distinct lines sharing the same ISLR concept
        self.env["account.move.line"].create({
            "move_id": invoice.id,
            "product_id": self.product_islr_iva_one.id,
            "quantity": 1,
            "price_unit": 50,
            "name": self.product_islr_iva_one.name,
        })
        retention = self._make_islr_retention_for(invoice)
        self.assertEqual(len(retention.retention_line_ids), 2)

        invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_islr_iva_one
        ).unlink()

        retention.action_recalculate(moves=invoice)

        remaining = retention.retention_line_ids
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining.payment_concept_id, self.concept_one)
        _logger.info("========= test_04 passed =========")

    def test_05_obsolete_line_with_posted_payment_raises(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        self.env["account.move.line"].create({
            "move_id": invoice.id,
            "product_id": self.product_islr_three.id,
            "quantity": 1,
            "price_unit": 100,
            "name": self.product_islr_three.name,
        })
        retention = self._make_islr_retention_for(invoice)
        self.assertEqual(len(retention.retention_line_ids), 2)

        # Simulate one of the retention lines already having a posted
        # payment, without going through the full reconciliation flow -
        # only the payment.state guard is under test here.
        posted_payment = self.env["account.payment"].create({
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_pnr_75.id,
            "journal_id": self.bank_journal_sup_ret.id,
            "amount": 1.0,
        })
        posted_payment.action_post()
        line_three = retention.retention_line_ids.filtered(
            lambda l: l.payment_concept_id == self.concept_three
        )
        line_three.payment_id = posted_payment.id

        invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_islr_three
        ).unlink()

        with self.assertRaises(UserError):
            retention.action_recalculate(moves=invoice)
        _logger.info("========= test_05 passed =========")

    def test_06_invoice_left_without_tax_raises(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        retention = self._make_iva_retention_for(invoice)

        invoice.invoice_line_ids.unlink()

        with self.assertRaises(UserError):
            retention.action_recalculate(moves=invoice)
        _logger.info("========= test_06 passed =========")

    def test_07_recalculate_scoped_to_triggering_invoice_only(self):
        invoice_a = self._create_two_rate_iva_invoice()
        invoice_b = self._create_invoice_reten_iva(
            150, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice_b.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})

        today = fields.Date.today()
        lines_a = self.env["account.retention"].compute_retention_lines_data(invoice_a)
        lines_b = self.env["account.retention"].compute_retention_lines_data(invoice_b)
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": today, "date_accounting": today,
            "retention_line_ids": [
                Command.create(data) for data in (lines_a + lines_b)
            ],
        })
        retention.action_post()
        self.assertEqual(len(retention.retention_line_ids), 3)

        lines_b_before = retention.retention_line_ids.filtered(
            lambda l: l.move_id == invoice_b
        )
        amounts_b_before = lines_b_before.mapped("retention_amount")

        invoice_a.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_iva_8
        ).unlink()

        retention.action_recalculate(moves=invoice_a)

        lines_b_after = retention.retention_line_ids.filtered(
            lambda l: l.move_id == invoice_b
        )
        self.assertEqual(lines_b_after.mapped("retention_amount"), amounts_b_before)
        self.assertEqual(
            len(retention.retention_line_ids.filtered(lambda l: l.move_id == invoice_a)),
            1,
        )
        _logger.info("========= test_07 passed =========")

    def test_08_client_retention_is_not_touched(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        today = fields.Date.today()
        lines_data = self.env["account.retention"].compute_retention_lines_data(invoice)
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "out_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": today, "date_accounting": today,
            "number": "12345678901234",
            "retention_line_ids": [Command.create(data) for data in lines_data],
        })
        for line in retention.retention_line_ids:
            line.retention_amount = line.retention_amount or 1.0
            line.foreign_retention_amount = line.foreign_retention_amount or 1.0
        retention.action_post()

        lines_before = retention.retention_line_ids.read(["aliquot", "retention_amount"])

        # Nothing must raise nor change: a client (out_invoice) retention
        # is out of scope for the recalculation entirely.
        retention.action_recalculate(moves=invoice)

        lines_after = retention.retention_line_ids.read(["aliquot", "retention_amount"])
        self.assertEqual(lines_before, lines_after)
        _logger.info("========= test_08 passed =========")
