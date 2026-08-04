import logging

from odoo import Command, fields, models
from odoo.tests import Form, TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_retention_credit_note")
class TestRetentionCreditNote(TransactionCase):
    """
    Regression tests for ticket #11353: retentions computed over credit notes
    (notas de credito) must use the opposite payment direction, must be picked
    up despite their negative amount_residual, must carry positive (abs)
    amounts on the retention line and must be netted (not summed) in the
    retention totals.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        bank_account = cls.env["account.account"].search(
            [("account_type", "=", "liquidity")], limit=1
        )
        transitory_account = cls.env["account.account"].search(
            [("account_type", "=", "other")], limit=1
        )
        profit_account = cls.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        loss_account = cls.env["account.account"].search(
            [("account_type", "=", "expense")], limit=1
        )

        payment_method_inbound = cls.env["account.payment.method"].create(
            {"name": "Manual In", "code": 90, "payment_type": "inbound"}
        )
        payment_method_outbound = cls.env["account.payment.method"].create(
            {"name": "Manual Out", "code": 91, "payment_type": "outbound"}
        )

        def _make_retention_journal(name, code):
            return cls.env["account.journal"].create(
                {
                    "name": name,
                    "code": code,
                    "type": "bank",
                    "company_id": cls.company.id,
                    "bank_account_id": bank_account.id,
                    "default_account_id": transitory_account.id,
                    "profit_account_id": profit_account.id,
                    "loss_account_id": loss_account.id,
                    "inbound_payment_method_line_ids": [
                        Command.create(
                            {"payment_method_id": payment_method_inbound.id, "name": "Manual"}
                        )
                    ],
                    "outbound_payment_method_line_ids": [
                        Command.create(
                            {"payment_method_id": payment_method_outbound.id, "name": "Manual"}
                        )
                    ],
                }
            )

        cls.iva_supplier_journal = _make_retention_journal("Retenciones IVA Prov NC", "RVPNC")
        cls.iva_customer_journal = _make_retention_journal("Retenciones IVA Cli NC", "RVCNC")
        cls.islr_supplier_journal = _make_retention_journal("Retenciones ISLR Prov NC", "RSPNC")
        cls.islr_customer_journal = _make_retention_journal("Retenciones ISLR Cli NC", "RSCNC")

        if not cls.company.currency_foreign_id:
            cls.company.currency_foreign_id = cls.env.ref("base.USD").id

        cls.company.write(
            {
                "iva_supplier_retention_journal_id": cls.iva_supplier_journal.id,
                "iva_customer_retention_journal_id": cls.iva_customer_journal.id,
                "islr_supplier_retention_journal_id": cls.islr_supplier_journal.id,
                "islr_customer_retention_journal_id": cls.islr_customer_journal.id,
            }
        )

        cls.tax_group_iva16 = cls.env["account.tax.group"].create({"name": "IVA 16% CN"})
        cls.tax_iva16 = cls.env["account.tax"].create(
            {
                "name": "IVA 16% CN",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": cls.tax_group_iva16.id,
            }
        )
        cls.tax_iva16_sale = cls.env["account.tax"].create(
            {
                "name": "IVA 16% CN Venta",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": cls.tax_group_iva16.id,
            }
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Prueba NC",
                "type": "service",
                "list_price": 100,
                "purchase_ok": True,
                "sale_ok": True,
                "supplier_taxes_id": [(6, 0, [cls.tax_iva16.id])],
                "taxes_id": [(6, 0, [cls.tax_iva16_sale.id])],
            }
        )

        cls.person_type = cls.env["type.person"].search([], limit=1) or cls.env[
            "type.person"
        ].create({"name": "Test Person Type NC"})

        cls.withholding_type = cls.env["account.withholding.type"].search(
            [("name", "=", "75%")], limit=1
        ) or cls.env["account.withholding.type"].search([], limit=1)

        cls.partner_supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor Prueba NC",
                "supplier_rank": 1,
                "type_person_id": cls.person_type.id,
                "withholding_type_id": cls.withholding_type.id if cls.withholding_type else False,
            }
        )
        cls.partner_customer = cls.env["res.partner"].create(
            {
                "name": "Cliente Prueba NC",
                "customer_rank": 1,
                "type_person_id": cls.person_type.id,
                "withholding_type_id": cls.withholding_type.id if cls.withholding_type else False,
            }
        )

        cls.purchase_journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "purchase")], limit=1
        )
        cls.sale_journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "sale")], limit=1
        )

        cls.payment_concept = cls.env["payment.concept"].create(
            {"name": "Concepto Prueba NC", "status": True}
        )
        cls.env["payment.concept.line"].create(
            {
                "type_person_id": cls.person_type.id,
                "payment_concept_id": cls.payment_concept.id,
                "code": 99,
                "percentage_tax_base": 100,
                "tariff_id": cls.env.ref(
                    "l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension"
                ).id,
                "pay_from": 0.0,
            }
        )
        cls.payment_concept.write(
            {"line_payment_concept_ids": [(6, 0, cls.payment_concept.line_payment_concept_ids.ids)]}
        )

    def _create_move(self, move_type, partner, base, journal, tax):
        if move_type in ("out_invoice", "out_refund"):
            self.__class__._correlative_counter = (
                getattr(self.__class__, "_correlative_counter", 500000) + 1
            )
            correlative = str(self.__class__._correlative_counter).zfill(5)
        else:
            correlative = False
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": fields.Date.today(),
                "correlative": correlative,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": base,
                            "tax_ids": [(6, 0, [tax.id])],
                        }
                    )
                ],
            }
        )
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def _build_islr_retention(self, retention_type, moves):
        with Form(
            self.env["account.retention"].with_context(
                default_type=retention_type, default_type_retention="islr"
            )
        ) as retention_form:
            retention_form.partner_id = moves[0].partner_id
            retention_form.date_accounting = fields.Date.today()
            if retention_type == "out_invoice":
                retention_form.number = "00000000000001"
        retention = retention_form.save()

        with Form(retention) as retention_form_edit:
            for move in moves:
                with retention_form_edit.retention_line_ids.new() as line:
                    line.move_id = move
                    line.payment_concept_id = self.payment_concept
        return retention_form_edit.save()

    def test_islr_payment_type_direction_supplier_invoice_and_credit_note(self):
        """
        Regla original rota:
            if move_type == "in_refund": payment_type = inbound/outbound
            if move_type == "out_refund": payment_type = outbound/inbound
        Sin `else`, un `move_type` "in_invoice" (el caso normal) nunca asignaba
        `payment_type`, produciendo un UnboundLocalError o reutilizando la
        direccion de la linea anterior. La correccion asigna siempre.
        """
        invoice = self._create_move(
            "in_invoice", self.partner_supplier, 1000.0, self.purchase_journal, self.tax_iva16
        )
        credit_note = self._create_move(
            "in_refund", self.partner_supplier, 200.0, self.purchase_journal, self.tax_iva16
        )

        retention = self._build_islr_retention("in_invoice", [invoice, credit_note])
        retention.action_post()

        invoice_line = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        refund_line = retention.retention_line_ids.filtered(lambda l: l.move_id == credit_note)

        self.assertEqual(
            invoice_line.payment_id.payment_type,
            "outbound",
            "Supplier retention over an invoice must create an outbound payment.",
        )
        self.assertEqual(
            refund_line.payment_id.payment_type,
            "inbound",
            "Supplier retention over a credit note must create an inbound payment "
            "(opposite direction to the invoice).",
        )

    def test_islr_payment_type_direction_customer_invoice_and_credit_note(self):
        invoice = self._create_move(
            "out_invoice", self.partner_customer, 1000.0, self.sale_journal, self.tax_iva16_sale
        )
        credit_note = self._create_move(
            "out_refund", self.partner_customer, 200.0, self.sale_journal, self.tax_iva16_sale
        )

        retention = self.env["account.retention"].create(
            {
                "type": "out_invoice",
                "type_retention": "islr",
                "partner_id": self.partner_customer.id,
                "number": "00000000000001",
                "date_accounting": fields.Date.today(),
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Test ISLR Line Invoice",
                            "move_id": invoice.id,
                            "payment_concept_id": self.payment_concept.id,
                            "invoice_amount": 1000.0,
                            "invoice_total": 1160.0,
                            "retention_amount": 30.0,
                            "foreign_invoice_amount": 1000.0,
                            "foreign_retention_amount": 30.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Test ISLR Line Credit Note",
                            "move_id": credit_note.id,
                            "payment_concept_id": self.payment_concept.id,
                            "invoice_amount": 200.0,
                            "invoice_total": 232.0,
                            "retention_amount": 6.0,
                            "foreign_invoice_amount": 200.0,
                            "foreign_retention_amount": 6.0,
                        }
                    ),
                ],
            }
        )
        retention.action_post()

        invoice_line = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        refund_line = retention.retention_line_ids.filtered(lambda l: l.move_id == credit_note)

        self.assertEqual(
            invoice_line.payment_id.payment_type,
            "inbound",
            "Customer retention over an invoice must create an inbound payment.",
        )
        self.assertEqual(
            refund_line.payment_id.payment_type,
            "outbound",
            "Customer retention over a credit note must create an outbound payment "
            "(opposite direction to the invoice).",
        )

    def test_iva_customer_retention_loads_credit_note_despite_negative_residual(self):
        """
        `amount_residual > 0` could exclude a credit note whenever its residual
        is zero or negative (`direction_sign` can flip the reported sign
        depending on move type and reconciliation state). The fix uses
        `amount_residual != 0`, so any open (non-reconciled) credit note must
        still be loaded as an available invoice for the retention.
        """
        invoice = self._create_move(
            "out_invoice", self.partner_customer, 1000.0, self.sale_journal, self.tax_iva16_sale
        )
        credit_note = self._create_move(
            "out_refund", self.partner_customer, 200.0, self.sale_journal, self.tax_iva16_sale
        )

        self.assertNotEqual(credit_note.amount_residual, 0.0)

        retention = self.env["account.retention"].with_context(
            default_type="out_invoice", default_type_retention="iva"
        ).new({"partner_id": self.partner_customer.id})
        retention._load_retention_lines_for_iva_customer_retention()

        available_ids = {
            (m.id.origin if isinstance(m.id, models.NewId) else m.id)
            for m in retention.available_invoice_ids
        }
        self.assertIn(invoice.id, available_ids)
        self.assertIn(
            credit_note.id,
            available_ids,
            "The credit note must be loaded as an available invoice for the IVA "
            "retention even though its amount_residual is negative.",
        )

    def test_retention_line_amounts_are_always_positive(self):
        """
        The retention voucher template applies the credit note sign itself
        (columns 13/14), so the retention line amounts must always come in
        as a positive magnitude, never signed.
        """
        credit_note = self._create_move(
            "in_refund", self.partner_supplier, 200.0, self.purchase_journal, self.tax_iva16
        )
        lines_data = self.env["account.retention"].compute_retention_lines_data(credit_note)

        self.assertTrue(lines_data)
        for line in lines_data:
            self.assertGreaterEqual(line["invoice_amount"], 0.0)
            self.assertGreaterEqual(line["iva_amount"], 0.0)
            self.assertGreaterEqual(line["invoice_total"], 0.0)
            self.assertGreaterEqual(line["retention_amount"], 0.0)

    def test_compute_totals_nets_credit_note_against_invoice(self):
        """
        `_compute_totals` must subtract credit note lines instead of summing
        everything, so the form totals match the printed voucher (which nets
        the credit note in columns 13/14).
        """
        invoice = self._create_move(
            "in_invoice", self.partner_supplier, 1000.0, self.purchase_journal, self.tax_iva16
        )
        credit_note = self._create_move(
            "in_refund", self.partner_supplier, 200.0, self.purchase_journal, self.tax_iva16
        )

        with Form(
            self.env["account.retention"].with_context(
                default_type="in_invoice", default_type_retention="iva"
            )
        ) as retention_form:
            retention_form.partner_id = self.partner_supplier
        retention = retention_form.save()

        invoice_line = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        refund_line = retention.retention_line_ids.filtered(lambda l: l.move_id == credit_note)

        self.assertAlmostEqual(retention.total_invoice_amount, 1000.0 - 200.0, places=2)
        self.assertAlmostEqual(
            retention.total_retention_amount,
            invoice_line.retention_amount - refund_line.retention_amount,
            places=2,
        )
