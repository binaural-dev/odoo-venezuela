from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.base.models.ir_actions_report import IrActionsReport
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestReportQuotationPrint(TransactionCase):
    """Una cotización en borrador debe poder imprimirse y enviarse por correo.

    El diálogo de envío de Odoo 19 renderiza el PDF del reporte al abrirse, así
    que cualquier restricción de impresión sobre sale.order inutiliza el botón
    "Enviar" de una cotización (ticket 14822).
    """

    def setUp(self):
        super().setUp()
        self.report_saleorder = 'sale.report_saleorder'
        self.report_invoice = 'account.account_invoices'

        self.account_receivable = self.env['account.account'].create({
            'name': 'Receivable', 'code': '1111111',
            'account_type': 'asset_receivable', 'reconcile': True,
        })
        self.account_revenue = self.env['account.account'].create({
            'name': 'Revenue', 'code': '4444444',
            'account_type': 'income',
        })
        self.journal_sale = self.env['account.journal'].create({
            'name': 'Sale Journal', 'type': 'sale',
            'code': 'SALE1',
            'default_account_id': self.account_revenue.id,
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'property_account_receivable_id': self.account_receivable.id,
        })
        self.product = self.env['product.product'].create({
            'name': 'Service Product',
            'type': 'service',
            'list_price': 100.0,
            'property_account_income_id': self.account_revenue.id,
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

    def test_01_render_html_draft_quotation(self):
        """El HTML del reporte de una cotización en borrador se genera."""
        self.assertEqual(self.order.state, 'draft')
        html, report_type = self.env['ir.actions.report']._render_qweb_html(
            self.report_saleorder, self.order.ids
        )
        self.assertEqual(report_type, 'html')
        self.assertIn(self.order.name, html.decode())

    def test_02_render_pdf_streams_draft_quotation(self):
        """El PDF de una cotización en borrador no se bloquea."""
        self.assertEqual(self.order.state, 'draft')
        with patch.object(
            IrActionsReport, '_render_qweb_pdf_prepare_streams', return_value={}
        ):
            self.env['ir.actions.report']._render_qweb_pdf_prepare_streams(
                self.report_saleorder, {}, res_ids=self.order.ids
            )

    def test_03_draft_invoice_still_blocked(self):
        """No se regresa el ticket 14012: la factura en borrador sigue bloqueada."""
        invoice = self.env['account.move'].with_context(check_move_validity=False).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': fields.Date.today(),
            'date': fields.Date.today(),
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100.0,
            })],
        })
        self.assertEqual(invoice.state, 'draft')
        with self.assertRaises(UserError):
            self.env['ir.actions.report']._render_qweb_pdf_prepare_streams(
                self.report_invoice, {}, res_ids=invoice.ids
            )
