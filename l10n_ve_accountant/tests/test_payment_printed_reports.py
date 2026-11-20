from markupsafe import escape

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_payment_printed_reports")
class TestPaymentPrintedReports(TransactionCase):
    """The printed reports of a payment show its data, not only their labels."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        currency_vef = cls.env.ref("base.VEF")
        currency_usd = cls.env.ref("base.USD")
        country_ve = cls.env.ref("base.ve")
        cls.company.write({
            "currency_id": currency_vef.id,
            "foreign_currency_id": currency_usd.id,
            "account_fiscal_country_id": country_ve.id,
            "country_id": country_ve.id,
            "external_report_layout_id": cls.env.ref("web.external_layout_standard").id,
        })
        today = fields.Date.today()
        Rate = cls.env["res.currency.rate"]
        for currency, rate in ((currency_vef, 1.0), (currency_usd, 40.0)):
            if not Rate.search([("name", "=", today), ("currency_id", "=", currency.id), ("company_id", "=", cls.company.id)]):
                Rate.create({"name": today, "currency_id": currency.id, "inverse_company_rate": rate, "company_id": cls.company.id})
        account_bank = cls.env["account.account"].create({
            "name": "Printed Reports Bank", "code": "100190", "account_type": "asset_cash",
            "company_ids": [(6, 0, cls.company.ids)],
        })
        manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.journal = cls.env["account.journal"].create({
            "name": "Printed Reports Bank",
            "type": "bank",
            "code": "PRBK",
            "default_account_id": account_bank.id,
            "outbound_payment_method_line_ids": [(0, 0, {
                "name": "Manual Out",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": account_bank.id,
            })],
        })
        cls.partner = cls.env["res.partner"].create({"name": "Printed Reports Supplier"})
        cls.bank_account = cls.env["res.partner.bank"].create({
            "account_number": "0102-1111-2222-3333-4444",
            "bank_name": "Printed Reports Bank Name",
            "partner_id": cls.partner.id,
        })
        cls.payment = cls.env["account.payment"].create({
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": cls.partner.id,
            "amount": 1500.0,
            "date": today,
            "journal_id": cls.journal.id,
            "partner_bank_id": cls.bank_account.id,
        })
        cls.payment.action_post()

    def _render(self, report_ref, docids, **kwargs):
        html = self.env["ir.actions.report"]._render_qweb_html(report_ref, docids, **kwargs)[0]
        return html.decode() if isinstance(html, bytes) else str(html)

    def test_payment_receipt_shows_the_recipient_bank_account(self):
        html = self._render("account.action_report_payment_receipt", self.payment.ids)
        self.assertIn("Printed Reports Bank Name - 0102-1111-2222-3333-4444", html)

    def test_payments_summary_shows_the_payments_of_the_journal(self):
        wizard = self.env["payment.report"].create({
            "payment_type": "outbound",
            "journal_id": self.journal.id,
            "start_date": self.payment.date,
            "end_date": self.payment.date,
        })
        action = wizard.generate_report_payment()
        html = self.env["ir.actions.report"].with_context(
            active_model="payment.report", active_id=wizard.id
        )._render_qweb_html("l10n_ve_accountant.action_report_all_payments", wizard.ids, data=action["data"])[0]
        html = html.decode() if isinstance(html, bytes) else str(html)
        self.assertIn(str(escape(self.journal.name)), html)
        self.assertIn(str(escape(self.payment.name)), html)
        self.assertIn(str(escape(self.partner.name)), html)
