from odoo import Command, fields
from odoo.tests import Form, tagged

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments

RATE = 40.0


@tagged("post_install", "-at_install", "l10n_ve_igtf_bi_igtf_order")
class TestBiIgtfDoesNotDependOnPaymentStateOrder(TestIndexedPayments):
    """``bi_igtf`` y ``igtf_top_aply`` no pueden quedar en 0 en una factura
    pagada solo porque ``payment_state`` aún no se había recalculado.

    Odoo recalcula ``amount_residual``, ``payment_state`` y ``bi_igtf`` en un
    orden que cambia entre procesos (semilla de hash). Si ``bi_igtf`` corre con
    el saldo en 0 y ``payment_state`` todavía en 'not_paid', antes se saltaba
    el cálculo y el 0 quedaba guardado. La prueba reproduce ese momento sin
    depender del azar: deja ``payment_state`` desactualizado a mano y vuelve a
    calcular.
    """

    def setUp(self):
        super().setUp()
        self.company.igtf_percentage = 3.0
        self.company.taxpayer_type = "special"
        self.invoice_date = self.payment_date
        self._set_rate(self.currency_usd, self.payment_date, RATE)
        mk = self.env["account.account"].create
        igtf_customer = mk({
            "name": "IGTF Customer", "code": "236000", "account_type": "liability_current",
            "company_ids": [(6, 0, [self.company.id])],
        })
        igtf_supplier = mk({
            "name": "IGTF Supplier", "code": "510000", "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.company.write({
            "customer_account_igtf_id": igtf_customer.id,
            "supplier_account_igtf_id": igtf_supplier.id,
        })
        self.partner.write({
            "default_advance_customer_account_id": igtf_customer.id,
            "default_advance_supplier_account_id": igtf_supplier.id,
            "taxpayer_type": "special",
        })
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        self.journal_igtf = self.env["account.journal"].sudo().create({
            "name": "Bank USD IGTF", "type": "bank", "code": "BUSDI",
            "currency_id": self.currency_usd.id, "is_igtf": True,
            "company_id": self.company.id, "default_account_id": self.account_bank.id,
            "inbound_payment_method_line_ids": [Command.create({
                "name": "In", "payment_method_id": manual_in.id,
                "payment_account_id": self.account_bank.id,
            })],
            "outbound_payment_method_line_ids": [Command.create({
                "name": "Out", "payment_method_id": manual_out.id,
                "payment_account_id": self.account_bank.id,
            })],
        })

    def _paid_invoice_with_igtf(self):
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as form:
            form.partner_id = self.partner
            form.journal_id = self.sale_journal
            form.invoice_date_display = self.invoice_date
            form.invoice_date = self.invoice_date
            form.currency_id = self.currency_usd
        invoice = form.save()
        with Form(invoice) as line_form:
            with line_form.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = line_form.save()
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay:
            pay.journal_id = self.journal_igtf
            pay.save()
            pay.currency_id = self.currency_usd
            pay.save()
            pay.payment_date = self.payment_date
            pay.save()
        pay.record._create_payments()
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        return invoice

    def _recompute_bi_igtf(self, invoice, stale_payment_state):
        """Calcula `bi_igtf` viendo `payment_state` desactualizado: se deja el
        valor viejo en el caché (sin escribir ni disparar recálculos), que es lo
        que ve el cálculo cuando Odoo lo corre antes que `payment_state`."""
        invoice.invalidate_recordset(["bi_igtf", "igtf_top_aply", "alter_bi_igtf", "foreign_bi_igtf"])
        self.env.cache.set(invoice, invoice._fields["payment_state"], stale_payment_state)
        self.assertEqual(invoice.payment_state, stale_payment_state)
        invoice.compute_bi_igtf()

    def test_stale_not_paid_state_does_not_zero_the_base(self):
        invoice = self._paid_invoice_with_igtf()
        expected = invoice.bi_igtf
        expected_top = invoice.igtf_top_aply
        self.assertGreater(expected, 0.0, "La factura pagada con IGTF debe tener base de IGTF.")

        # Momento del recálculo con el saldo ya en 0 y el estado todavía viejo.
        self._recompute_bi_igtf(invoice, "not_paid")

        self.assertAlmostEqual(invoice.bi_igtf, expected, places=2)
        self.assertAlmostEqual(invoice.igtf_top_aply, expected_top, places=2)

    def test_reversed_invoice_keeps_no_base(self):
        invoice = self._paid_invoice_with_igtf()
        self._recompute_bi_igtf(invoice, "reversed")
        self.assertEqual(invoice.bi_igtf, 0.0)
        self.assertEqual(invoice.igtf_top_aply, 0.0)

    def test_draft_invoice_without_payments_has_no_base(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id, "currency_id": self.currency_usd.id,
            "invoice_date": self.invoice_date,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "quantity": 1, "price_unit": 100.0,
                "account_id": self.account_income.id,
            })],
        })
        self.assertEqual(invoice.bi_igtf, 0.0)
