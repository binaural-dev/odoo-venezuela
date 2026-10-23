from lxml import etree

from odoo import fields
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_islr_foreign_amount")
class TestRetentionISLRForeignAmount(RetentionTestCommon):
    """Monto en moneda alterna de una línea ISLR con compañía en base VEF.

    Antes se tomaba la base en USD como si fuera Bs y se convertía otra vez a USD, con lo que
    el monto quedaba dividido dos veces entre la tasa. Ahora sale del Bs retenido entre la tasa
    de la factura, igual que en IVA y municipal.

    La valoración foreign solo existe en retenciones indexadas (ver `test_retention_indexed.py`).
    """

    def _post_supplier_islr_invoice(self, amount=1000.0):
        invoice = self._create_invoice_islr(
            amount=amount, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def test_non_indexed_islr_line_has_no_foreign_valuation(self):
        """Una línea no indexada no tiene valoración foreign: ni monto ni tasa ni fecha de tasa.
        Antes el monto se convertía dos veces y quedaba en 0 sin que nadie lo notara."""
        invoice = self._post_supplier_islr_invoice()
        line = invoice.retention_islr_line_ids[0]

        self.assertEqual(line.retention_amount, 27.0)
        # Igual que antes: la moneda foránea de la línea es la alterna de la compañía
        self.assertEqual(line.foreign_currency_id, line.company_id.foreign_currency_id)
        self.assertEqual(line.foreign_retention_amount, 0.0)
        self.assertEqual(line._get_foreign_retention_amount(27.0), 0.0)

    def test_arcv_data_has_only_company_currency_amounts(self):
        invoice = self._post_supplier_islr_invoice()
        retention = invoice.retention_islr_line_ids[0].retention_id
        today = fields.Date.today()

        wizard = self.env["arcv.report"].create({
            "partner_id": retention.partner_id.id,
            "date_start": today,
            "date_end": today,
        })
        grouped = wizard._get_islr_retention_lines_grouped_by_year_month_and_percentage_fees()
        data = wizard._construct_report_data(grouped)

        self.assertEqual(len(data["retentions"]), 1)
        entry = data["retentions"][0]
        self.assertEqual(entry["total_invoice_amount"], 1000.0)
        self.assertEqual(entry["total_retention_amount"], 27.0)
        self.assertNotIn("total_foreign_invoice_amount", entry)
        self.assertNotIn("total_foreign_retention_amount", entry)

        html, _report_type = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_payment_extension.action_report_arcv", [], data=data
        )
        self.assertIn(b"Comprobante", html)

    def test_islr_retention_amount_is_readonly_for_all_supplier_documents(self):
        """ISLR debe bloquear la edición del monto retenido en todos los documentos de
        proveedor (factura, nota de crédito y de débito), igual que IVA."""
        supplier_types = "parent.type in ('in_invoice', 'in_refund', 'in_debit')"
        islr = self.env.ref("l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension")
        municipal = self.env.ref(
            "l10n_ve_payment_extension.view_retention_municipal_form_l10n_ve_payment_extension"
        )
        for view in (islr, municipal):
            self.assertNotIn("parent.type == 'in_invoice'", view.arch_db, view.name)

        islr_node = etree.fromstring(islr.arch_db).xpath("//field[@name='retention_amount']")
        self.assertEqual([n.get("readonly") for n in islr_node], [supplier_types])
        # En municipal el monto retenido siempre se calcula (base x alícuota): nunca se edita
        municipal_node = etree.fromstring(municipal.arch_db).xpath("//field[@name='retention_amount']")
        self.assertEqual([n.get("readonly") for n in municipal_node], ["1"])

    def test_retention_line_rate_is_readonly_in_every_view(self):
        """La tasa de la línea es solo referencial (las conversiones salen de la tasa de la fecha),
        así que ninguna vista debe permitir editarla."""
        for xmlid in (
            "l10n_ve_payment_extension.view_retention_iva_form_l10n_ve_payment_extension",
            "l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension",
            "l10n_ve_payment_extension.view_retention_municipal_form_l10n_ve_payment_extension",
        ):
            arch = etree.fromstring(self.env.ref(xmlid).arch_db)
            nodes = arch.xpath("//field[@name='foreign_currency_rate']")
            self.assertTrue(nodes, xmlid)
            for node in nodes:
                self.assertEqual(node.get("readonly"), "1", xmlid)

    def test_legacy_unused_line_fields_were_removed(self):
        """Campos heredados de versiones anteriores que ningún flujo escribe ni lee."""
        fields_ = self.env["account.retention.line"]._fields
        for name in ("amount_tax_ret", "base_ret", "imp_ret", "retention_rate", "display_invoice_number"):
            self.assertNotIn(name, fields_)
