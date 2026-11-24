import random
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
COL_DATE, COL_INVOICE, COL_DEBIT, COL_CREDIT, COL_TYPE, COL_AFFECTED, COL_BASE = 0, 1, 3, 4, 5, 6, 9
# Columnas de la fila del comprobante de retencion de ISLR.
COL_ISLR_TD, COL_ISLR_NUMBER = 0, 1


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
        # La comun deja el pais fiscal distinto del pais de la compania (el de los impuestos); la
        # reversion valida el pais de los impuestos (`_validate_taxes_country`) y la NC no se crearia.
        self.company.account_fiscal_country_id = self.company.country_id
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
            self.assertTrue(document.debit_origin_id, name)
            expected = ("--", name, "--", "02-REG", document.debit_origin_id.name)
        else:
            self.assertTrue(document.reversed_entry_id, "La nota de credito %s nace de una factura." % name)
            expected = ("--", "--", name, "03-REG", document.reversed_entry_id.name)
        got = (tds[COL_INVOICE], tds[COL_DEBIT], tds[COL_CREDIT], tds[COL_TYPE], tds[COL_AFFECTED])
        self.assertEqual(got, expected, "Fila del comprobante de %s (%s)" % (name, kind))
        # La nota de credito resta: su base imponible sale en negativo; la factura y la ND suman.
        base = tds[COL_BASE]
        self.assertTrue(any(c in "123456789" for c in base), "Base imponible en cero en %s: %s" % (name, base))
        self.assertEqual(base.startswith("-"), kind == "credit", "Signo de la base de %s (%s): %s" % (name, kind, base))

    def _credit(self, doc_type, auto_iva=False):
        """Nota de credito publicada, creada con el asistente de reversion desde una factura
        publicada, como la crea el usuario (con `reversed_entry_id`). Es parcial (la mitad): al
        publicarse se concilia con su origen, y una NC total dejaria la factura pagada y fuera de
        la retencion de IVA."""
        origin = self._document(doc_type.replace("_refund", "_invoice"), "iva")
        wizard = Form(self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=origin.ids,
        ))
        wizard.reason = "Devolucion"
        wizard.journal_id = origin.journal_id
        action = wizard.save().refund_moves()
        credit = self.env["account.move"].browse(action["res_id"])
        with Form(credit) as form_credit:
            if doc_type.startswith("in_"):
                form_credit.correlative = str(random.randint(10000000000000, 99999999999999))
            with form_credit.invoice_line_ids.edit(0) as line:
                line.price_unit = self.AMOUNT / 2
        credit.write({
            "date": self.doc_date, "invoice_date": self.doc_date, "invoice_date_display": self.doc_date,
            **({"generate_iva_retention": True} if auto_iva else {}),
        })
        credit.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(credit.move_type, doc_type)
        self.assertEqual(credit.reversed_entry_id, origin)
        return credit

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

    def _mixed_supplier_documents(self, credit_from_origin=True):
        """Facturas y notas intercaladas, en el orden en que se crean: factura, nota de debito (con su
        factura de origen), factura, nota de debito (con su origen) y nota de credito.

        `credit_from_origin`: la NC nace del asistente de reversion (con factura afectada). Al
        publicarse queda conciliada con su origen y sin saldo, y una retencion no se puede publicar
        sobre un documento sin saldo; para publicar la retencion se usa una NC con saldo abierto
        (sin origen)."""
        inv_a = self._document("in_invoice", "iva")
        nd_b = self._document("in_debit", "iva")
        inv_c = self._document("in_invoice", "iva")
        nd_d = self._document("in_debit", "iva")
        nc_e = self._credit("in_refund") if credit_from_origin else self._document("in_refund", "iva")
        kinds = [
            (inv_a, "invoice"),
            (nd_b.debit_origin_id, "invoice"),
            (nd_b, "debit"),
            (inv_c, "invoice"),
            (nd_d.debit_origin_id, "invoice"),
            (nd_d, "debit"),
            (nc_e, "credit"),
        ]
        if credit_from_origin:
            kinds.insert(-1, (nc_e.reversed_entry_id, "invoice"))
        return kinds

    # ------------------------------------------------------------------ #
    # El documento
    # ------------------------------------------------------------------ #
    def test_01_is_debit_note_by_document(self):
        invoice = self._document("in_invoice", "iva")
        debit = self._document("in_debit", "iva")
        credit = self._credit("in_refund")
        self.assertFalse(debit.journal_id.is_debit, "La nota nace en el diario normal de compras.")
        self.assertEqual(debit.company_id, debit.debit_origin_id.company_id,
                         "El asistente crea la ND en la compania de su origen.")
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
        credit = self._credit("in_refund")
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
        kinds = self._mixed_supplier_documents(credit_from_origin=False)
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
        credit = self._credit("out_refund")
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
            if kind == "credit":
                document = self._credit(doc_type, auto_iva=True)
            else:
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
                expected = ("03", document.reversed_entry_id.name)
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
                expected = ("NC", "03-REG", "--", "--", name, document.reversed_entry_id.name)
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
    def _pdf_title(self, document, lang=None):
        content, _ = self.env["ir.actions.report"].with_context(lang=lang or self.env.lang)._render_qweb_html(PDF_REF, document.ids)
        return " ".join(lxml_html.fromstring(content).xpath("string(//h2)").split())

    def test_60_standard_pdf_title(self):
        invoice = self._document("in_invoice", "iva")
        debit = self._document("in_debit", "iva")
        credit = self._credit("in_refund")
        self.assertTrue(self._pdf_title(invoice).startswith("Vendor Bill"))
        self.assertTrue(self._pdf_title(debit).startswith("Vendor Debit Note"))
        self.assertTrue(self._pdf_title(credit).startswith("Vendor Credit Note"))

    def test_62_standard_pdf_title_es_ve(self):
        """En es_VE la factura de proveedor normal sigue con el titulo traducido de `account` (la
        herencia no reemplaza ese texto) y la nota de debito sale rotulada con el de este modulo."""
        self.env["res.lang"]._activate_lang("es_VE")
        self.env["ir.module.module"].search(
            [("name", "in", ("account", "l10n_ve_invoice"))]
        )._update_translations(["es_VE"], overwrite=True)
        invoice = self._document("in_invoice", "iva")
        debit = self._document("in_debit", "iva")
        # El PDF se imprime en el idioma del contacto.
        invoice.partner_id.lang = "es_VE"
        self.assertEqual(self._pdf_title(invoice, "es_VE").split(" ")[:3], ["Factura", "de", "proveedor"])
        self.assertTrue(self._pdf_title(debit, "es_VE").startswith("Nota de débito de proveedor"))

    def test_61_free_form_title(self):
        """El titulo del formato libre es exactamente el del documento, y la ND muestra su factura
        afectada."""
        invoice = self._document("out_invoice", "iva")
        debit = self._document("out_debit", "iva")
        credit = self._credit("out_refund")

        def nfc(text):
            return unicodedata.normalize("NFC", " ".join(text.split()))

        for document, title in ((invoice, "FACTURA"), (debit, "NOTA DE DÉBITO"), (credit, "NOTA DE CRÉDITO")):
            content, _ = self.env["ir.actions.report"]._render_qweb_html(FREE_FORM_REF, document.ids)
            tree = lxml_html.fromstring(content)
            titles = [nfc(span.text_content()) for span in tree.xpath("//div[hasclass('text-center')]/span")]
            self.assertEqual(titles, [nfc(title)], document.name)
            if document == debit:
                self.assertIn(nfc("Factura afectada: %s" % debit.debit_origin_id.name), nfc(tree.text_content()))

    # ------------------------------------------------------------------ #
    # Fecha propia de la nota de debito
    # ------------------------------------------------------------------ #
    def test_70_debit_note_date_is_its_own(self):
        """El comprobante y el TXT imprimen la fecha de la nota, no la de su factura de origen."""
        debit = self._document("in_debit", "iva", debit_date=self.accounting_date)
        origin = debit.debit_origin_id
        self.assertNotEqual(debit.invoice_date_display, origin.invoice_date_display)
        retention = self._retention_from_form("iva", debit)
        tds = self._row_for(self._voucher_rows(retention), debit)
        self.assertEqual(debit.invoice_date, origin.invoice_date, "La tasa sigue siendo la del origen.")
        self.assertEqual(tds[COL_DATE], self.accounting_date.strftime("%d/%m/%Y"))
        self.assertNotEqual(tds[COL_DATE], origin.invoice_date_display.strftime("%d/%m/%Y"))
        row = {r["Número de documento"]: r for r in self.IvaWizard._retention_iva(retention)}[debit.name]
        self.assertEqual(row["Fecha de factura"], self.accounting_date.strftime("%Y-%m-%d"))

    # ------------------------------------------------------------------ #
    # Nota de credito en un diario is_debit: sale como nota de credito
    # ------------------------------------------------------------------ #
    def test_31_credit_note_in_is_debit_journal(self):
        self.purchase_journal.is_debit = True
        credit = self._credit("in_refund")
        self.assertTrue(credit.journal_id.is_debit)
        retention = self._retention_from_form("iva", credit)
        tds = self._row_for(self._voucher_rows(retention), credit)
        self.assertEqual((tds[COL_INVOICE], tds[COL_DEBIT], tds[COL_CREDIT], tds[COL_TYPE]),
                         ("--", "--", credit.name, "03-REG"))
        row = {r["Número de documento"]: r for r in self.IvaWizard._retention_iva(retention)}[credit.name]
        self.assertEqual(row["Tipo de documento"], "03")
        line = next(l for l in self._purchase_book() if credit.name == l["credit_note_number"])
        self.assertEqual((line["move_type"], line["transaction_type"], line["debit_note_number"] or "--"),
                         ("NC", "03-REG", "--"))

    # ------------------------------------------------------------------ #
    # Libro de ventas
    # ------------------------------------------------------------------ #
    def _sale_book(self):
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "company_id": self.company.id,
            "date_from": fields.Date.subtract(self.accounting_date, days=30),
            "date_to": self.accounting_date,
        })
        return wizard.parse_sale_book_data()

    def _sale_line(self, lines, document):
        line = next((l for l in lines if document.name in (
            l["invoice_number"], l["debit_note_number"], l["credit_note_number"])), None)
        self.assertTrue(line, "El libro de ventas no tiene %s" % document.name)
        return line

    def test_51_sale_book_native_debit_note(self):
        invoice = self._document("out_invoice", "iva")
        debit = self._document("out_debit", "iva")
        credit = self._credit("out_refund")
        lines = self._sale_book()
        line = self._sale_line(lines, invoice)
        self.assertEqual((line["move_type"], line["transaction_type"], line["number_invoice_affected"]),
                         ("FAC", "01-REG", "--"))
        line = self._sale_line(lines, debit)
        self.assertEqual((line["move_type"], line["transaction_type"], line["debit_note_number"],
                          line["invoice_number"], line["number_invoice_affected"]),
                         ("ND", "02-REG", debit.name, "--", debit.debit_origin_id.name))
        line = self._sale_line(lines, credit)
        self.assertEqual((line["move_type"], line["transaction_type"], line["number_invoice_affected"]),
                         ("NC", "03-REG", credit.reversed_entry_id.name))

    def test_52_sale_book_debit_note_in_is_debit_journal(self):
        """Nota de debito de cliente en un diario dedicado `is_debit`, sin factura de origen."""
        self.sale_journal.is_debit = True
        debit = self._document("out_invoice", "iva")
        self.assertFalse(debit.debit_origin_id)
        line = self._sale_line(self._sale_book(), debit)
        self.assertEqual((line["move_type"], line["transaction_type"], line["debit_note_number"]),
                         ("ND", "02-REG", debit.name))

    # ------------------------------------------------------------------ #
    # Comprobante de ISLR: columna TD
    # ------------------------------------------------------------------ #
    def _islr_rows(self, retention):
        content, _ = self.env["ir.actions.report"]._render_qweb_html(VOUCHER_REF, retention.ids)
        rows = []
        for tr in lxml_html.fromstring(content).xpath("//tbody/tr"):
            tds = [" ".join(td.text_content().split()) for td in tr.xpath("./td")]
            if len(tds) >= 8:
                rows.append(tds)
        return rows

    def test_80_islr_voucher_document_type(self):
        """El comprobante de ISLR rotula FA / ND / NC por el documento: la ND de proveedor en el
        diario normal de compras sale como ND, igual que en el de IVA."""
        # La comun agrega a `concept_one` un segundo tramo para el mismo tipo de persona que el de los
        # datos, y `_get_code_of_retention` espera uno solo: se deja solo el de la prueba.
        (self.concept_one.line_payment_concept_ids.filtered(
            lambda l: l.type_person_id == self.islr_concept_line.type_person_id
        ) - self.islr_concept_line).unlink()
        invoice = self._document("in_invoice", "islr")
        debit = self._document("in_debit", "islr")
        self.assertFalse(debit.journal_id.is_debit)
        for document, td in ((invoice, "FA"), (debit, "ND")):
            retention = self._retention_from_form("islr", document)
            row = next((r for r in self._islr_rows(retention) if r[COL_ISLR_NUMBER] == document.name), None)
            self.assertTrue(row, "El comprobante de ISLR no tiene fila para %s" % document.name)
            self.assertEqual(row[COL_ISLR_TD], td, document.name)
