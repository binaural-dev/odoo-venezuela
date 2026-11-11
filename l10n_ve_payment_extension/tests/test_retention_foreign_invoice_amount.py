# Ticket #15730: with VEF as company currency, `_compute_amounts` multiplied the
# Bs amount by `foreign_currency_rate` (Bs per USD) instead of dividing it, so the
# USD base of an ISLR retention line came out inflated (57,082.20 Bs -> 44,953,374 USD).
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_retention_foreign_amount")
class TestRetentionForeignInvoiceAmount(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.company.write({"currency_id": cls.vef.id, "currency_foreign_id": cls.usd.id})
        cls.env["res.currency.rate"].create({
            "name": fields.Date.today(), "currency_id": cls.usd.id,
            "inverse_company_rate": 787.52, "company_id": cls.company.id,
        })
        cls.partner = cls.env["res.partner"].create({"name": "ISLR Partner"})
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "purchase")], limit=1
        )
        cls.product = cls.env["product.product"].create({"name": "ISLR Service", "type": "service"})
        cls.invoice = cls.env["account.move"].create({
            "partner_id": cls.partner.id,
            "move_type": "in_invoice",
            "journal_id": cls.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, {"product_id": cls.product.id, "price_unit": 100.0})],
        })

    def _line(self, rate, foreign_invoice_amount):
        return self.env["account.retention.line"].create({
            "name": "ISLR line",
            "move_id": self.invoice.id,
            "invoice_total": 57082.20,
            "invoice_amount": 57082.20,
            "retention_amount": 1712.47,
            "foreign_currency_rate": rate,
            "foreign_invoice_amount": foreign_invoice_amount,
            "foreign_retention_amount": 2.17,
        })

    def _recompute_from_origin(self, line):
        draft = line.new({}, origin=line)
        draft._compute_amounts()
        return draft

    def test_bs_to_usd_divides_by_rate(self):
        """USD base = Bs base / rate (Bs per USD), never Bs x rate."""
        line = self._line(787.52, 72.48)
        draft = self._recompute_from_origin(line)
        self.assertAlmostEqual(draft.foreign_invoice_amount, 57082.20 / 787.52, places=2)
        self.assertLess(draft.foreign_invoice_amount, draft.invoice_amount)
        self.assertAlmostEqual(draft.invoice_amount, 57082.20, places=2)

    def test_zero_rate_keeps_persisted_usd_amount(self):
        """Without a rate there is nothing to convert with: keep the stored USD amount
        instead of raising ZeroDivisionError or zeroing it."""
        line = self._line(0.0, 72.48)
        draft = self._recompute_from_origin(line)
        self.assertAlmostEqual(draft.foreign_invoice_amount, 72.48, places=2)

    def _islr_draft(self, subtract_fees):
        concept = self.env["payment.concept"].create({"name": "ISLR concept 15730"})
        return self.env["account.retention.line"].new({
            "move_id": self.invoice.id,
            "payment_concept_id": concept.id,
            "invoice_amount": 10000.0,
            "foreign_invoice_amount": 12.70,
            "related_percentage_tax_base": 100.0,
            "related_percentage_fees": 3.0,
            "related_amount_subtract_fees": subtract_fees,
            "foreign_currency_rate": 787.52,
        })

    def test_islr_subtrahend_is_converted_to_usd(self):
        """The subtrahend is in Bs: the USD retention must subtract subtrahend / rate,
        not the raw Bs figure (19.29 Bs made a 0.38 USD retention come out as 18.91)."""
        draft = self._islr_draft(19.29)
        draft._compute_retention_amount()
        rate = draft.foreign_currency_rate
        self.assertAlmostEqual(draft.retention_amount, 10000.0 * 0.03 - 19.29, places=2)
        self.assertAlmostEqual(
            draft.foreign_retention_amount, 12.70 * 0.03 - 19.29 / rate, places=2
        )
        # Both currencies describe the same retention.
        self.assertAlmostEqual(
            draft.foreign_retention_amount, draft.retention_amount / rate, places=1
        )

    def test_islr_without_subtrahend_unchanged(self):
        draft = self._islr_draft(0.0)
        draft._compute_retention_amount()
        self.assertAlmostEqual(draft.foreign_retention_amount, 12.70 * 0.03, places=2)

    def test_depends_cover_line_rate(self):
        """The stored computes must be recomputed when the line rate changes."""
        Line = self.env["account.retention.line"]
        self.assertIn("foreign_currency_rate", Line._fields["foreign_invoice_amount"].get_depends(Line)[0])
        self.assertIn("foreign_currency_rate", Line._fields["foreign_retention_amount"].get_depends(Line)[0])

    def test_islr_uses_line_rate_not_invoice_rate(self):
        """A later change of the invoice rate must not alter the retention: the
        conversion uses the rate stored on the line."""
        draft = self._islr_draft(19.29)
        self.invoice.foreign_rate = 1000.0
        draft._compute_retention_amount()
        self.assertAlmostEqual(
            draft.foreign_retention_amount, 12.70 * 0.03 - 19.29 / 787.52, places=2
        )
