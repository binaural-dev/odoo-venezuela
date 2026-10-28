from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestContingencyNameEditable(TransactionCase):
    """On a contingency journal the invoice number is typed by hand, so the
    number field must stay editable when Odoo has no sequence preview to show
    (task 83188).

    Odoo only shows the field when the invoice has a number, a preview
    (name_placeholder) or quick edit mode, and shows a fixed "Draft"
    otherwise. Switching a draft to another journal clears its number, and
    the preview only exists while the journal has no previous number. So an
    invoice created from a sale order on the default journal and then moved
    to a contingency journal that was already used was left showing "Draft";
    the first invoice of a new contingency journal still worked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Contingency Customer"})
        cls.contingency_journal = cls.env["account.journal"].create({
            "name": "Contingency Test",
            "code": "CTGT",
            "type": "sale",
            "is_contingency": True,
        })
        cls.sale_journal = cls.env["account.journal"].create({
            "name": "Regular Sales Test",
            "code": "RSLT",
            "type": "sale",
        })
        cls.other_sale_journal = cls.env["account.journal"].create({
            "name": "Other Sales Test",
            "code": "OSLT",
            "type": "sale",
        })

    def _invoice(self, journal, **vals):
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            **vals,
        })

    def test_number_editable_after_switching_to_used_contingency_journal(self):
        # A previous hand-typed number, like "3536" in the report.
        self._invoice(self.contingency_journal, name="3536", correlative="3536")
        # Created on the default journal, the way a sale order creates it.
        invoice = self._invoice(self.sale_journal)

        with Form(invoice) as form:
            form.journal_id = self.contingency_journal
            self.assertFalse(form.name, "Precondition: switching journal clears the number")
            self.assertFalse(form.name_placeholder, "Precondition: no sequence preview")
            form.name = "3537"
            form.correlative = "3537"
        self.assertEqual(invoice.name, "3537")
        self.assertEqual(invoice.correlative, "3537")

    def test_regular_journal_keeps_draft_label(self):
        self._invoice(self.other_sale_journal, name="OSLT/2026/00001")
        invoice = self._invoice(self.sale_journal)
        with Form(invoice) as form:
            form.journal_id = self.other_sale_journal
            self.assertFalse(form.is_contingency)
            with self.assertRaises(AssertionError):
                form.name = "OSLT/2026/00099"
