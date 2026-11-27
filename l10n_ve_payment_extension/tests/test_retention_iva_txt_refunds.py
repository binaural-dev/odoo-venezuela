from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_iva_txt_refunds")
class TestRetentionIvaTxtRefunds(RetentionTestCommon):
    """El TXT de retenciones de IVA del SENIAT debe incluir los comprobantes
    de notas de crédito de proveedor (type = in_refund), no solo facturas.

    Todo el flujo se arma como lo haría un usuario: facturas con Form, nota de
    crédito con el asistente de reversión, la retención IVA que nace al publicar
    (y que el usuario aprueba) y el TXT con el Form del asistente de Generar TXT.
    """

    def setUp(self):
        super().setUp()
        self.IvaWizard = self.env["wizard.retention.iva"]
        self.Retention = self.env["account.retention"]
        self.today = fields.Date.today()
        self.company.partner_id.write({"prefix_vat": "J", "vat": "123456789"})
        self.partner = self.partner_pnr_75
        if not self.partner.prefix_vat:
            self.partner.write({"prefix_vat": "J"})
        # La copia de la factura (reversión) revalida el país de los impuestos
        # contra el país fiscal de la compañía; el fixture común usa otro país.
        self.product_iva.supplier_taxes_id.write({
            "country_id": self.company.account_fiscal_country_id.id,
        })
        self.control_counter = 0

    # ------------------------------------------------------------------
    # Pasos de usuario
    # ------------------------------------------------------------------
    def _control(self):
        self.control_counter += 1
        return "00-%06d" % self.control_counter

    def _user_creates_bill(self, amount, journal=None, generate_iva=True,
                           correlative="auto", debit_origin=None):
        """Usuario crea y publica una factura de proveedor desde el Form."""
        journal = journal or self.purchase_journal
        with Form(self.env["account.move"].with_context(
            default_move_type="in_invoice", default_journal_id=journal.id,
        )) as form:
            form.partner_id = self.partner
            form.invoice_date = self.today
            form.currency_id = self.currency_vef
            if correlative == "auto":
                correlative = self._control()
            if correlative:
                form.correlative = correlative
        bill = form.save()
        if debit_origin:
            # En la UI el origen lo fija el asistente de nota de débito
            # (campo de solo lectura en el Form).
            bill.debit_origin_id = debit_origin
        with Form(bill) as form:
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = amount
            if generate_iva:
                form.generate_iva_retention = True
        bill = form.save()
        bill.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        bill.action_post()
        return bill

    def _user_creates_credit_note(self, bill, correlative="auto", generate_iva=True):
        """Usuario usa 'Agregar nota de crédito' (asistente de reversión)."""
        with Form(self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=bill.ids,
        )) as wiz_form:
            wiz_form.reason = "Devolución"
        action = wiz_form.save().refund_moves()
        refund = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(refund.move_type, "in_refund")
        self.assertEqual(refund.reversed_entry_id, bill)
        if correlative == "auto":
            correlative = self._control()
        with Form(refund) as form:
            if correlative:
                form.correlative = correlative
            if generate_iva:
                form.generate_iva_retention = True
        refund = form.save()
        refund.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        refund.action_post()
        return refund

    def _user_approves_retention(self, move):
        """La retención IVA nace del posteo; el usuario la aprueba (emite)."""
        retention = self.Retention.search([
            ("type_retention", "=", "iva"),
            ("retention_line_ids.move_id", "=", move.id),
        ])
        self.assertEqual(len(retention), 1, "Debe existir 1 retención IVA para %s" % move.name)
        if retention.state == "draft":
            retention.action_post()
        self.assertEqual(retention.state, "emitted")
        return retention

    def _user_opens_txt_wizard(self):
        with Form(self.IvaWizard) as form:
            form.date_start = self.today.replace(day=1)
            form.date_end = self.today
        return form.save()

    def _download(self):
        """Ejecuta el controlador real (misma URL que abre el asistente)."""
        from odoo.addons.l10n_ve_payment_extension.controllers import iva_report

        fake_request = SimpleNamespace(
            env=self.env,
            make_response=lambda f, headers: f.read(),
        )
        with patch.object(iva_report, "request", fake_request):
            body = iva_report.GenerateTxt().download_retention_iva_txt(
                str(self.today.replace(day=1)), str(self.today), self.company.id,
            )
        text = body.get_data(as_text=True) if hasattr(body, "get_data") else body
        return [l.split("\t") for l in text.splitlines() if l]

    # ------------------------------------------------------------------
    # Bug: NC de proveedor fuera del TXT
    # ------------------------------------------------------------------
    def test_01_refund_retention_type_and_line(self):
        """Flujo: factura -> NC -> retención de la NC. Valida el dato de la línea."""
        bill = self._user_creates_bill(1000.0)
        self._user_approves_retention(bill)
        refund = self._user_creates_credit_note(bill)
        ret = self._user_approves_retention(refund)

        self.assertEqual(ret.type, "in_refund")
        data = self.IvaWizard._retention_iva(ret)
        self.assertEqual(len(data), 1)
        line = data[0]
        self.assertEqual(line["Tipo de documento"], "03")
        self.assertEqual(line["Número del documento afectado"], bill.name)
        self.assertEqual(line["Número de documento"], refund.name)
        self.assertEqual(line["Número de control"], refund.correlative)
        # Duda 3: los montos de la NC deben salir positivos en el TXT.
        self.assertGreater(line["Base imponible"], 0)
        self.assertGreater(line["Monto del Iva Retenido"], 0)
        self.assertEqual(line["Alícuota"], 16.0)

    def test_02_wizard_only_refund_retentions_in_period(self):
        """Solo quedan retenciones de NC en el período: no debe dar
        'No retentions found'. El usuario anula el comprobante de la factura."""
        bill = self._user_creates_bill(1000.0)
        bill_ret = self._user_approves_retention(bill)
        refund = self._user_creates_credit_note(bill)
        self._user_approves_retention(refund)
        bill_ret.action_cancel()
        self.assertEqual(bill_ret.state, "cancel")
        emitted = self.Retention.search([("type_retention", "=", "iva"), ("state", "=", "emitted")])
        self.assertEqual(emitted.mapped("type"), ["in_refund"])
        action = self._user_opens_txt_wizard().generate_txt()
        self.assertEqual(action["type"], "ir.actions.act_url")

    def test_03_wizard_without_retentions_still_fails(self):
        with self.assertRaises(UserError):
            self._user_opens_txt_wizard().generate_txt()

    def test_04_txt_includes_invoice_and_refund(self):
        bill = self._user_creates_bill(1000.0)
        self._user_approves_retention(bill)
        refund = self._user_creates_credit_note(bill)
        self._user_approves_retention(refund)
        self._user_opens_txt_wizard().generate_txt()

        rows = self._download()
        self.assertEqual(sorted(r[4] for r in rows), ["01", "03"])
        refund_row = next(r for r in rows if r[4] == "03")
        self.assertEqual(refund_row[6], refund.name)
        self.assertEqual(refund_row[7], refund.correlative)
        self.assertEqual(refund_row[11], bill.name)
        self.assertEqual(next(r for r in rows if r[4] == "01")[6], bill.name)

    def test_05_txt_invoices_unchanged(self):
        """Sin NC en el período, el TXT sigue saliendo solo con facturas."""
        bills = [self._user_creates_bill(amt) for amt in (1000.0, 700.0, 300.0)]
        for bill in bills:
            self._user_approves_retention(bill)
        rows = self._download()
        self.assertEqual(sorted(r[6] for r in rows), sorted(b.name for b in bills))
        self.assertEqual({r[4] for r in rows}, {"01"})

    def test_06_wizard_and_controller_share_domain(self):
        """El conteo del asistente y la descarga usan el mismo criterio."""
        bill = self._user_creates_bill(1000.0)
        self._user_approves_retention(bill)
        refund = self._user_creates_credit_note(bill)
        self._user_approves_retention(refund)
        domain = self.IvaWizard._get_retention_iva_domain(
            self.today.replace(day=1), self.today, self.company.id)
        self.assertEqual(self.Retention.search_count(domain), len(self._download()))

    # ------------------------------------------------------------------
    # Duda 1: notas de débito / type in_debit
    # ------------------------------------------------------------------
    def _debit_journal(self):
        return self.purchase_journal.copy({
            "name": "Notas de Débito Test", "code": "NDT", "is_debit": True,
        })

    def test_07_debit_note_retention_type_and_txt(self):
        """Una ND de proveedor (diario is_debit) genera retención type in_invoice
        y sale en el TXT con tipo 02 y su documento afectado."""
        bill = self._user_creates_bill(1000.0, generate_iva=False)
        debit = self._user_creates_bill(
            200.0, journal=self._debit_journal(), debit_origin=bill,
        )
        ret = self._user_approves_retention(debit)
        self.assertEqual(
            ret.type, "in_invoice",
            "Si esto fuese in_debit, la ND quedaría fuera del TXT.",
        )
        rows = self._download()
        row = next(r for r in rows if r[6] == debit.name)
        self.assertEqual(row[4], "02")
        self.assertEqual(row[11], bill.name)

    # ------------------------------------------------------------------
    # Duda 2: documento afectado de una ND sin origen
    # ------------------------------------------------------------------
    def test_08_debit_note_without_origin_affected_doc_is_zero(self):
        debit = self._user_creates_bill(200.0, journal=self._debit_journal())
        ret = self._user_approves_retention(debit)
        data = self.IvaWizard._retention_iva(ret)
        self.assertEqual(data[0]["Tipo de documento"], "02")
        self.assertEqual(data[0]["Número del documento afectado"], "0")
        row = self._download()[0]
        self.assertEqual(row[11], "0")

    # ------------------------------------------------------------------
    # Duda 4: NC sin número de control
    # ------------------------------------------------------------------
    def test_09_refund_without_control_number_does_not_break_txt(self):
        bill = self._user_creates_bill(1000.0)
        self._user_approves_retention(bill)
        refund = self._user_creates_credit_note(bill, correlative=False)
        self._user_approves_retention(refund)
        rows = self._download()
        self.assertEqual(sorted(r[4] for r in rows), ["01", "03"])
