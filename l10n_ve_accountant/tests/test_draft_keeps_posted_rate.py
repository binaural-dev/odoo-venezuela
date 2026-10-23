from odoo import Command, fields
from odoo.tests import Form, tagged

from .test_indexed_payments import TestIndexedPayments

POSTED_RATE = 884.75
NEW_RATE = 900.0


@tagged("post_install", "-at_install", "l10n_ve_accountant_draft_keeps_posted_rate")
class TestDraftKeepsPostedRate(TestIndexedPayments):
    """
    Restablecer a borrador una factura confirmada tras editar la tasa de su día
    conserva la tasa de confirmación: el asiento sigue balanceado y todas sus
    líneas (ventas, IVA y CxC) mantienen sus importes y la tasa mostrada.
    """

    def setUp(self):
        super().setUp()
        self._set_rate(self.currency_usd, self.invoice_date, POSTED_RATE)
        tax16 = self.env["account.tax"].create({
            "name": "IVA 16% incluido",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.test_tax_group.id,
            "price_include_override": "tax_included",
        })
        self.invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "invoice_date": self.invoice_date,
            "date": self.invoice_date,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id, "quantity": 1, "price_unit": 60.0,
                    "account_id": self.account_income.id, "tax_ids": [Command.set([tax16.id])],
                }),
                Command.create({
                    "product_id": self.product.id, "quantity": 1, "price_unit": 40.0,
                    "account_id": self.account_income.id, "tax_ids": [Command.set([self.test_tax.id])],
                }),
            ],
        })
        self.invoice.with_context(move_action_post_alert=True).action_post()

    def _rates(self):
        return (
            self.invoice.foreign_rate,
            self.invoice.foreign_inverse_rate,
            self.invoice.invoice_currency_rate,
            self.invoice.move_currency_to_company_currency_rate,
        )

    def _balances(self):
        return {line.id: (line.balance, line.amount_currency) for line in self.invoice.line_ids}

    def _as_new_request(self):
        """The 'already distributed' marks live in the cursor's cache for the
        whole transaction; a real web request starts without them."""
        self.env.flush_all()
        self.env.invalidate_all()
        cache = self.env.cr.cache
        cache.pop(("_real_portion_distributed", self.invoice.id), None)
        cache.pop("_dynamic_lines_in_progress", None)

    def test_reset_to_draft_after_day_rate_change_keeps_posted_rate(self):
        before, rates_before = self._balances(), self._rates()
        self._set_rate(self.currency_usd, self.invoice_date, NEW_RATE)
        self._as_new_request()
        self.assertAlmostEqual(
            self.invoice.move_currency_to_company_currency_rate, POSTED_RATE, places=4,
            msg="Aun confirmada, el formulario no debe mostrar la tasa nueva del día.",
        )

        self.invoice.button_draft()  # must not raise "The entry is not balanced."

        self.assertEqual(self.invoice.state, "draft")
        self.assertEqual(self._rates(), rates_before, "Las tasas del documento no se recalculan.")
        self.assertEqual(
            self._balances(), before,
            "Ninguna línea debe recalcularse con la tasa nueva del día.",
        )
        self.assertAlmostEqual(
            sum(self.invoice.line_ids.mapped("balance")), 0.0, places=2,
            msg="El asiento debe quedar balanceado.",
        )

    def test_all_lines_keep_the_posted_rate_after_reset_to_draft(self):
        """Ninguna línea (ventas, IVA o cuenta por cobrar) queda convertida
        con la tasa nueva mientras otras conservan la anterior."""
        self._set_rate(self.currency_usd, self.invoice_date, NEW_RATE)
        self._as_new_request()

        self.invoice.button_draft()

        for line in self.invoice.line_ids:
            amount = abs(line.amount_currency)
            self.assertLess(
                abs(abs(line.balance) - amount * POSTED_RATE),
                abs(abs(line.balance) - amount * NEW_RATE),
                f"La línea {line.account_id.code} ({line.display_type}) quedó más cerca de la tasa nueva que de la original.",
            )

    def test_repost_after_draft_keeps_posted_alternate_rate(self):
        """Draft -> post again: la tasa alterna (y con ella las columnas
        alternas) sigue siendo la de la primera confirmación."""
        before, rates_before = self._balances(), self._rates()
        self._set_rate(self.currency_usd, self.invoice_date, NEW_RATE)
        self._as_new_request()

        self.invoice.button_draft()
        self._as_new_request()
        self.invoice.with_context(move_action_post_alert=True).action_post()

        self.assertEqual(self.invoice.state, "posted")
        self.assertEqual(self._rates(), rates_before, "La tasa alterna cambió al volver a confirmar.")
        self.assertEqual(self._balances(), before)

    def test_rewriting_same_date_on_reset_draft_keeps_posted_rates(self):
        """Escribir la misma fecha en el borrador (RPC, importación, otro
        módulo) no recalcula las tasas con la tasa nueva del día: Odoo
        recalcula al escribir una dependencia aunque el valor no cambie."""
        rates_before = self._rates()
        self._set_rate(self.currency_usd, self.invoice_date, NEW_RATE)
        self._as_new_request()
        self.invoice.button_draft()
        self._as_new_request()

        self.invoice.write({"invoice_date": self.invoice_date, "date": self.invoice_date})

        self.assertEqual(self._rates(), rates_before, "La fecha reescrita recalculó las tasas.")

    def test_form_date_changed_and_restored_keeps_posted_alternate_rate(self):
        """Formulario del borrador: la fecha se cambia y se devuelve a la
        original antes de guardar. El onchange recalcula el registro virtual
        con la fecha intermedia y, al volver, no debe quedar la tasa nueva del
        día sino la de la confirmación."""
        day = self.invoice_date
        other_day = fields.Date.subtract(day, days=1)
        self._set_rate(self.currency_usd, other_day, 870.0)
        self.invoice = self.invoice.copy(
            {"invoice_date": day, "invoice_date_display": day, "date": day}
        )
        self.invoice.with_context(move_action_post_alert=True).action_post()
        rates_before = self._rates()
        self._set_rate(self.currency_usd, day, NEW_RATE)
        self._as_new_request()
        self.invoice.button_draft()
        self._as_new_request()

        with Form(self.invoice) as form:
            form.invoice_date_display = other_day
            form.invoice_date_display = day
        self._as_new_request()

        self.assertEqual(
            self.invoice.invoice_date, day, "La fecha de tasa debe quedar en la original."
        )
        self.assertEqual(
            (self.invoice.foreign_rate, self.invoice.foreign_inverse_rate),
            rates_before[:2],
            "Guardar el formulario recalculó la tasa alterna.",
        )

    def test_form_real_date_change_on_reset_draft_saves_new_rate(self):
        """Formulario del borrador restablecido: cambiar la fecha a otro día
        recalcula la tasa y al guardar debe quedar la del nuevo día."""
        other_day = fields.Date.subtract(self.invoice_date, days=1)
        self._set_rate(self.currency_usd, other_day, 870.0)
        self.invoice.button_draft()
        self._as_new_request()

        with Form(self.invoice) as form:
            form.invoice_date_display = other_day
        self._as_new_request()

        self.assertEqual(self.invoice.invoice_date, other_day)
        self.assertAlmostEqual(self.invoice.foreign_rate, 870.0, places=4)
        self.assertAlmostEqual(self.invoice.move_currency_to_company_currency_rate, 870.0, places=4)

    def test_form_rate_date_change_on_reset_draft_saves_new_rate(self):
        """Igual, pero editando la "Rate Date" (invoice_date) directamente."""
        other_day = fields.Date.subtract(self.invoice_date, days=1)
        self._set_rate(self.currency_usd, other_day, 870.0)
        self.invoice.button_draft()
        self._as_new_request()

        with Form(self.invoice) as form:
            form.invoice_date = other_day
        self._as_new_request()

        self.assertEqual(self.invoice.invoice_date, other_day)
        self.assertAlmostEqual(self.invoice.foreign_rate, 870.0, places=4)
        self.assertAlmostEqual(self.invoice.move_currency_to_company_currency_rate, 870.0, places=4)

    def _purchase_invoice_reset_to_draft(self):
        journal = self.env["account.journal"].sudo().create({
            "name": "Compras tasa", "type": "purchase", "code": "CMPR",
            "company_id": self.company.id,
        })
        payable = self.env["account.account"].create({
            "name": "CxP tasa", "code": "211999", "account_type": "liability_payable",
            "reconcile": True,
        })
        self.partner.property_account_payable_id = payable
        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "currency_id": self.currency_usd.id,
            "invoice_date": self.invoice_date,
            "invoice_date_display": self.invoice_date,
            "date": self.invoice_date,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "quantity": 1, "price_unit": 100.0,
                "account_id": self.account_income.id,
            })],
        })
        bill.with_context(move_action_post_alert=True).action_post()
        bill.button_draft()
        self._as_new_request()
        return bill

    def test_form_rate_date_change_on_purchase_reset_draft_saves_new_rate(self):
        """Compras: la tasa sale de invoice_date (Rate Date), como en ventas."""
        other_day = fields.Date.subtract(self.invoice_date, days=1)
        self._set_rate(self.currency_usd, other_day, 870.0)
        bill = self._purchase_invoice_reset_to_draft()

        with Form(bill) as form:
            form.invoice_date = other_day
        self._as_new_request()

        self.assertEqual(bill.invoice_date, other_day)
        self.assertAlmostEqual(bill.foreign_rate, 870.0, places=4)

    def test_changing_the_date_of_a_reset_draft_does_recompute_rates(self):
        """La protección no congela la tasa si la fecha realmente cambia."""
        other_date = fields.Date.subtract(self.invoice_date, days=1)
        self._set_rate(self.currency_usd, other_date, 870.0)
        self.invoice.button_draft()
        self._as_new_request()

        self.invoice.write({"invoice_date": other_date})

        self.assertAlmostEqual(self.invoice.foreign_rate, 870.0, places=4)
        self.assertAlmostEqual(self.invoice.move_currency_to_company_currency_rate, 870.0, places=4)

    def test_rewriting_same_date_on_never_posted_draft_still_recomputes(self):
        """Un borrador que nunca se confirmó sigue tomando la tasa vigente."""
        draft = self.invoice.copy({"invoice_date": self.invoice_date})
        self._set_rate(self.currency_usd, self.invoice_date, NEW_RATE)
        self._as_new_request()

        draft.write({"invoice_date": self.invoice_date})

        self.assertAlmostEqual(draft.foreign_rate, NEW_RATE, places=4)


@tagged("post_install", "-at_install", "l10n_ve_accountant_draft_keeps_posted_rate")
class TestDraftKeepsPostedRateVefInvoice(TestDraftKeepsPostedRate):
    """Same scenario for an invoice booked in company currency (VEF), whose
    alternate-currency (USD) columns are the ones converted with the rate."""

    def setUp(self):
        super().setUp()
        self.invoice = self.invoice.copy({"currency_id": self.currency_vef.id, "invoice_date": self.invoice_date})
        self.invoice.with_context(move_action_post_alert=True).action_post()

    def _foreign(self):
        return {
            line.id: (round(line.foreign_debit, 2), round(line.foreign_credit, 2), round(line.foreign_balance, 2))
            for line in self.invoice.line_ids
        }

    def test_reset_to_draft_keeps_alternate_currency_amounts(self):
        before_balances, before_foreign, before_rate = self._balances(), self._foreign(), self.invoice.foreign_rate
        rates_before = self._rates()
        self._set_rate(self.currency_usd, self.invoice_date, NEW_RATE)
        self._as_new_request()

        self.invoice.button_draft()

        self.assertEqual(self._balances(), before_balances)
        self.assertEqual(self.invoice.foreign_rate, before_rate)
        self.assertEqual(self._rates(), rates_before)
        self.assertAlmostEqual(self.invoice.move_currency_to_company_currency_rate, POSTED_RATE, places=4)
        self.assertEqual(
            self._foreign(), before_foreign,
            "Las columnas alternas no deben recalcularse con la tasa nueva del día.",
        )
