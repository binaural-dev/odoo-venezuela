import unicodedata

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval

from .retention_flow_helpers import RetentionFlowHelpers
from .test_withholding_common_VEF import RetentionTestCommon

VOUCHER_REF = "l10n_ve_payment_extension.retention_voucher_template"
PDF_REF = "account.report_invoice_with_payments"
FREE_FORM_REF = "l10n_ve_invoice.template_invoice_free_form_l10n_ve_invoice"

# Columnas de la fila del comprobante de retencion de IVA.
COL_INVOICE, COL_DEBIT, COL_CREDIT, COL_TYPE, COL_AFFECTED = 1, 3, 4, 5, 6


@tagged("post_install", "-at_install", "debit_note_detection")
class TestDebitNoteDetection(RetentionFlowHelpers, RetentionTestCommon):
    """Una nota de debito se identifica por el documento (`debit_origin_id`) y no solo por el diario.

    La nota de debito nativa (`account.debit.note`) nace en el mismo diario de su factura, que no tiene
    `is_debit`: el comprobante de retencion, el PDF, el TXT de retenciones y los libros la mostraban como
    factura. Cubre la retencion creada con `Form` y la creada sola al publicar (`generate_iva_retention`),
    con facturas, notas de debito y de credito intercaladas en una misma retencion."""

    def setUp(self):
        super().setUp()
        self.accounting_date = fields.Date.today()
        self.doc_date = fields.Date.subtract(self.accounting_date, days=3)
        self._set_rates(380.0, 400.0)
        self.IvaWizard = self.env["wizard.retention.iva"]

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #
    def _voucher_rows(self, retention):
        content, _ = self.env["ir.actions.report"]._render_qweb_html(VOUCHER_REF, retention.ids)
        rows = []
        for tr in lxml_html.fromstring(content).xpath("//tr"):
            tds = [" ".join(td.text_content().split()) for td in tr.xpath("./td")]
            if len(tds) >= 8:
                rows.append(tds)
        return rows

    def _row_for(self, rows, document):
        for tds in rows:
            if document.name in (tds[COL_INVOICE], tds[COL_DEBIT], tds[COL_CREDIT]):
                return tds
        self.fail("El comprobante no tiene fila para %s: %s" % (document.name, rows))

    def _assert_voucher_row(self, rows, document, kind):
        tds = self._row_for(rows, document)
        name = document.name
        if kind == "invoice":
            expected = (name, "--", "--", "01-REG", "--")
        elif kind == "debit":
            expected = ("--", name, "--", "02-REG", document.debit_origin_id.name)
        else:
            expected = ("--", "--", name, "03-REG", document.reversed_entry_id.name or "--")
        got = (tds[COL_INVOICE], tds[COL_DEBIT], tds[COL_CREDIT], tds[COL_TYPE], tds[COL_AFFECTED])
        self.assertEqual(got, expected, "Fila del comprobante de %s (%s)" % (name, kind))

    def _retention_form_multi(self, documents, side="supplier"):
        """Retencion de IVA creada con `Form` desde la accion de su menu, con exactamente estos
        documentos como lineas (en el orden en que el formulario los carga o los agrega)."""
        action = self.env.ref(f"l10n_ve_payment_extension.action_retention_iva_{side}").read()[0]
        ctx = safe_eval(action.get("context", "{}"))
        view = "l10n_ve_payment_extension.view_retention_iva_form_l10n_ve_payment_extension"
        with Form(self.env[action["res_model"]].with_context(ctx), view=view) as form:
            form.partner_id = documents[0].partner_id
            form.date_accounting = self.accounting_date
            present = self.env["account.move"]
            for idx in reversed(range(len(form.retention_line_ids))):
                with form.retention_line_ids.edit(idx) as line:
                    keep = line.move_id in documents
                    if keep:
                        present |= line.move_id
                if not keep:
                    form.retention_line_ids.remove(idx)
            for document in documents - present:
                with form.retention_line_ids.new() as line:
                    line.move_id = document
        return form.save()

    def _mixed_supplier_documents(self):
        """Facturas y notas intercaladas, en el orden en que se crean: factura, nota de debito (con su
        factura de origen), factura, nota de debito (con su origen) y nota de credito."""
        inv_a = self._document("in_invoice", "iva")
        nd_b = self._document("in_debit", "iva")
        inv_c = self._document("in_invoice", "iva")
        nd_d = self._document("in_debit", "iva")
        nc_e = self._document("in_refund", "iva")
        kinds = [
            (inv_a, "invoice"),
            (nd_b.debit_origin_id, "invoice"),
            (nd_b, "debit"),
            (inv_c, "invoice"),
            (nd_d.debit_origin_id, "invoice"),
            (nd_d, "debit"),
            (nc_e, "credit"),
        ]
        return kinds

    # ------------------------------------------------------------------ #
    # El documento
    # ------------------------------------------------------------------ #
    def test_01_is_debit_note_by_document(self):
        invoice = self._document("in_invoice", "iva")
        debit = self._document("in_debit", "iva")
        credit = self._document("in_refund", "iva")
        self.assertFalse(debit.journal_id.is_debit, "La nota nace en el diario normal de compras.")
        self.assertFalse(invoice._is_debit_note())
        self.assertTrue(debit._is_debit_note())
        self.assertFalse(credit._is_debit_note())
        self.assertFalse(debit.debit_origin_id._is_debit_note())

    def test_02_is_debit_note_by_journal(self):
        """Un documento en un diario `is_debit` sigue siendo nota de debito, tenga o no origen."""
        invoice = self._form_document("in_invoice", "iva", 1000.0)
        self.assertFalse(invoice._is_debit_note())
        self.purchase_journal.is_debit = True
        self.assertTrue(invoice._is_debit_note())
        self.assertFalse(invoice.debit_origin_id)

    def test_03_credit_note_is_never_debit_note(self):
        credit = self._document("in_refund", "iva")
        credit.journal_id.is_debit = True
        self.assertFalse(credit._is_debit_note())

    # ------------------------------------------------------------------ #
    # Comprobante: creado a mano con Form
    # ------------------------------------------------------------------ #
    def test_10_supplier_voucher_form_mixed_lines(self):
        kinds = self._mixed_supplier_documents()
        retention = self._retention_form_multi(self.env["account.move"].union(*[d for d, _ in kinds]))
        self.assertEqual(len(retention.retention_line_ids.mapped("move_id")), len(kinds))
        rows = self._voucher_rows(retention)
        for document, kind in kinds:
            self._assert_voucher_row(rows, document, kind)

    def test_11_supplier_payment_sign_unchanged(self):
        """La nota de debito de proveedor suma deuda, como la factura: su pago va en el mismo sentido.
        Solo la nota de credito se invierte."""
        kinds = self._mixed_supplier_documents()
        retention = self._retention_form_multi(self.env["account.move"].union(*[d for d, _ in kinds]))
        retention.action_post()
        for document, kind in kinds:
            line = retention.retention_line_ids.filtered(lambda l: l.move_id == document)
            self.assertTrue(line.payment_id, document.name)
            expected = "inbound" if kind == "credit" else "outbound"
            self.assertEqual(line.payment_id.payment_type, expected, "%s (%s)" % (document.name, kind))

    def test_12_supplier_voucher_form_single_debit_note(self):
        debit = self._document("in_debit", "iva")
        retention = self._retention_from_form("iva", debit)
        self._assert_voucher_row(self._voucher_rows(retention), debit, "debit")

    def test_13_customer_voucher_form_debit_note(self):
        debit = self._document("out_debit", "iva")
        self.assertFalse(debit.journal_id.is_debit)
        retention = self._retention_from_form("iva", debit)
        self._assert_voucher_row(self._voucher_rows(retention), debit, "debit")

    def test_14_customer_voucher_form_invoice_and_credit_unchanged(self):
        invoice = self._document("out_invoice", "iva")
        credit = self._document("out_refund", "iva")
        self._assert_voucher_row(self._voucher_rows(self._retention_from_form("iva", invoice)), invoice, "invoice")
        self._assert_voucher_row(self._voucher_rows(self._retention_from_form("iva", credit)), credit, "credit")

    # ------------------------------------------------------------------ #
    # Comprobante: creado solo al publicar
    # ------------------------------------------------------------------ #
    def _auto_retention(self, document):
        retention = document.retention_iva_line_ids.mapped("retention_id")
        self.assertTrue(retention, "Al publicar se crea la retencion de %s." % document.name)
        return retention

    def test_20_supplier_voucher_auto_invoice_debit_credit(self):
        for doc_type, kind in (("in_invoice", "invoice"), ("in_debit", "debit"), ("in_refund", "credit")):
            document = self._document(doc_type, "iva", auto_iva=True)
            retention = self._auto_retention(document)
            self._assert_voucher_row(self._voucher_rows(retention), document, kind)

    def test_21_supplier_auto_debit_note_header_and_lines_like_invoice(self):
        """La retencion automatica de la nota de debito se arma igual que la de la factura."""
        invoice = self._document("in_invoice", "iva", auto_iva=True)
        debit = self._document("in_debit", "iva", auto_iva=True)
        ret_invoice = self._auto_retention(invoice)
        ret_debit = self._auto_retention(debit)
        self.assertEqual(ret_debit.type, ret_invoice.type)
        self.assertEqual(ret_debit.state, ret_invoice.state)
        self.assertEqual(
            ret_debit.retention_line_ids.mapped("retention_amount"),
            ret_invoice.retention_line_ids.mapped("retention_amount"),
        )
        self.assertEqual(
            ret_debit.payment_ids.mapped("payment_type"), ret_invoice.payment_ids.mapped("payment_type"),
        )

    # ------------------------------------------------------------------ #
    # Diario con is_debit: sigue funcionando igual
    # ------------------------------------------------------------------ #
    def test_30_voucher_debit_note_in_is_debit_journal(self):
        self.purchase_journal.is_debit = True
        invoice = self._document("in_invoice", "iva")
        self.assertFalse(invoice.debit_origin_id)
        retention = self._retention_from_form("iva", invoice)
        tds = self._row_for(self._voucher_rows(retention), invoice)
        self.assertEqual(
            (tds[COL_INVOICE], tds[COL_DEBIT], tds[COL_TYPE]), ("--", invoice.name, "02-REG"),
        )

    # ------------------------------------------------------------------ #
    # TXT de retenciones de IVA
    # ------------------------------------------------------------------ #
    def test_40_txt_document_type_and_affected(self):
        kinds = self._mixed_supplier_documents()
        retention = self._retention_form_multi(self.env["account.move"].union(*[d for d, _ in kinds]))
        data = {row["Número de documento"]: row for row in self.IvaWizard._retention_iva(retention)}
        for document, kind in kinds:
            row = data[document.name]
            if kind == "invoice":
                expected = ("01", "0")
            elif kind == "debit":
                expected = ("02", document.debit_origin_id.name)
            else:
                expected = ("03", document.reversed_entry_id.name or "0")
            self.assertEqual(
                (row["Tipo de documento"], row["Número del documento afectado"]), expected,
                "%s (%s)" % (document.name, kind),
            )

    # ------------------------------------------------------------------ #
    # Libro de compras
    # ------------------------------------------------------------------ #
    def _purchase_book(self):
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "purchase",
            "company_id": self.company.id,
            "date_from": fields.Date.subtract(self.accounting_date, days=30),
            "date_to": self.accounting_date,
        })
        return wizard.parse_purchase_book_data()

    def test_50_purchase_book_debit_note_columns(self):
        kinds = self._mixed_supplier_documents()
        lines = self._purchase_book()
        for document, kind in kinds:
            line = next(
                (l for l in lines if document.name in (
                    l["invoice_number"], l["debit_note_number"], l["credit_note_number"])),
                None,
            )
            self.assertTrue(line, "El libro de compras no tiene %s" % document.name)
            name = document.name
            if kind == "invoice":
                expected = ("FAC", "01-REG", name, "--", "--", "--")
            elif kind == "debit":
                expected = ("ND", "02-REG", "--", name, "--", document.debit_origin_id.name)
            else:
                expected = ("NC", "03-REG", "--", "--", name, document.reversed_entry_id.name or "--")
            got = tuple(
                (line[key] or "--") if line[key] != "" else "--"
                for key in (
                    "move_type", "transaction_type", "invoice_number",
                    "debit_note_number", "credit_note_number", "number_invoice_affected",
                )
            )
            self.assertEqual(got, expected, "%s (%s)" % (name, kind))

    # ------------------------------------------------------------------ #
    # PDF estandar y formato libre
    # ------------------------------------------------------------------ #
    def _pdf_title(self, document):
        content, _ = self.env["ir.actions.report"]._render_qweb_html(PDF_REF, document.ids)
        return " ".join(lxml_html.fromstring(content).xpath("string(//h2)").split())

    def test_60_standard_pdf_title(self):
        invoice = self._document("in_invoice", "iva")
        debit = self._document("in_debit", "iva")
        credit = self._document("in_refund", "iva")
        self.assertTrue(self._pdf_title(invoice).startswith("Vendor Bill"))
        self.assertTrue(self._pdf_title(debit).startswith("Vendor Debit Note"))
        self.assertTrue(self._pdf_title(credit).startswith("Vendor Credit Note"))

    def test_61_free_form_title(self):
        invoice = self._document("out_invoice", "iva")
        debit = self._document("out_debit", "iva")
        credit = self._document("out_refund", "iva")
        for document, title in ((invoice, "FACTURA"), (debit, "NOTA DE DÉBITO"), (credit, "NOTA DE CRÉDITO")):
            content, _ = self.env["ir.actions.report"]._render_qweb_html(FREE_FORM_REF, document.ids)
            text = unicodedata.normalize("NFC", " ".join(lxml_html.fromstring(content).text_content().split()))
            self.assertIn(unicodedata.normalize("NFC", title), text, document.name)
