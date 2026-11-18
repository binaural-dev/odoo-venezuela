from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_payment_register_retention")
class TestPaymentRegisterRetention(TransactionCase):
    """
    Regression tests for ticket #14366: `_get_context_invoices` on the
    `account.payment.register` wizard must resolve exactly the invoices that
    are actually going to be paid, not every invoice that happened to be
    selected alongside them (e.g. from a list view where an already-collected
    invoice of the same partner is selected together with a pending one).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        bank_account = cls.env["account.account"].search(
            [("account_type", "=", "liquidity")], limit=1
        )
        transitory_account = cls.env["account.account"].search(
            [("account_type", "=", "other")], limit=1
        )
        profit_account = cls.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        loss_account = cls.env["account.account"].search(
            [("account_type", "=", "expense")], limit=1
        )

        payment_method_inbound = cls.env["account.payment.method"].create(
            {"name": "Manual In Reg", "code": 92, "payment_type": "inbound"}
        )

        cls.bank_journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "bank")], limit=1
        )

        cls.iva_customer_journal = cls.env["account.journal"].create(
            {
                "name": "Retenciones IVA Cli Reg",
                "code": "RVCREG",
                "type": "bank",
                "company_id": cls.company.id,
                "bank_account_id": bank_account.id,
                "default_account_id": transitory_account.id,
                "profit_account_id": profit_account.id,
                "loss_account_id": loss_account.id,
                "inbound_payment_method_line_ids": [
                    Command.create(
                        {"payment_method_id": payment_method_inbound.id, "name": "Manual"}
                    )
                ],
            }
        )
        cls.company.write({"iva_customer_retention_journal_id": cls.iva_customer_journal.id})

        # Fija ambas monedas explicitamente (no solo la alterna) para no depender de
        # cual sea la moneda de la compania en la base sobre la que corra el test --
        # ver tests/test_retention_credit_note.py, que fija el mismo par por la misma razon.
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.company.write(
            {
                "currency_id": cls.currency_usd.id,
                "currency_foreign_id": cls.currency_vef.id,
            }
        )
        # Sin una tasa real, _compute_rate_for_documents (l10n_ve_accountant) sobreescribe
        # foreign_rate/foreign_inverse_rate a 0 y _prepare_tax_totals (l10n_ve_tax) revienta
        # con "No hay moneda extranjera configurada en la empresa" al postear la factura.
        cls.currency_vef.write(
            {
                "rate_ids": [
                    Command.create({"company_rate": 2.0, "name": fields.Date.today()})
                ],
            }
        )

        cls.tax_group_iva16 = cls.env["account.tax.group"].create({"name": "IVA 16% Reg"})
        cls.tax_iva16_sale = cls.env["account.tax"].create(
            {
                "name": "IVA 16% Reg Venta",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": cls.tax_group_iva16.id,
            }
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Prueba Reg",
                "type": "service",
                "list_price": 100,
                "sale_ok": True,
                "taxes_id": [(6, 0, [cls.tax_iva16_sale.id])],
            }
        )

        cls.withholding_type = cls.env["account.withholding.type"].search(
            [("name", "=", "75%")], limit=1
        ) or cls.env["account.withholding.type"].search([], limit=1)
        cls.partner_customer = cls.env["res.partner"].create(
            {
                "name": "Cliente Prueba Reg",
                "customer_rank": 1,
                "withholding_type_id": cls.withholding_type.id if cls.withholding_type else False,
            }
        )

        cls.sale_journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "sale")], limit=1
        )

    def _create_invoice(self, amount):
        # Assigning the correlative manually sidesteps `is_valid_to_sequence`'s
        # auto-numbering (l10n_ve_invoice), whose predict-then-check-for-duplicates
        # logic in `action_post` is unreliable when posting more than one invoice
        # per test transaction and is unrelated to what this test covers.
        # Starts high to avoid colliding with `invoice.correlative`'s real
        # ir.sequence prediction: it uses a non-transactional Postgres sequence
        # under the hood, so its counter survives test rollbacks across runs.
        self.__class__._correlative_counter = (
            getattr(self.__class__, "_correlative_counter", 90000) + 1
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_customer.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": fields.Date.today(),
                "correlative": str(self.__class__._correlative_counter).zfill(5),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [(6, 0, [self.tax_iva16_sale.id])],
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _pay_invoice_in_full(self, invoice):
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "journal_id": self.bank_journal.id,
                }
            )
        )
        wizard._create_payments()
        invoice.invalidate_recordset(["amount_residual", "payment_state"])

    def test_get_context_invoices_from_move_lines(self):
        """
        active_model == account.move.line (the "Register Payment" button on the
        invoice form) must resolve to exactly the invoice behind those journal
        items -- regression for ticket #14366.
        """
        invoice = self._create_invoice(1000.0)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move.line", active_ids=invoice.line_ids.ids)
            .create({})
        )
        self.assertEqual(wizard._get_context_invoices(), invoice)

    def test_get_context_invoices_from_moves(self):
        """
        active_model == account.move (e.g. selection from a list view) must also
        resolve to exactly the selected invoice.
        """
        invoice = self._create_invoice(1000.0)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({})
        )
        self.assertEqual(wizard._get_context_invoices(), invoice)

    def test_onchange_via_form_resolves_correct_invoice(self):
        """
        Regression for the assumption the fix relies on: `line_ids` must reach
        the onchange's fields_spec because it's declared `invisible="1"` in the
        base wizard view, not because `create({})` happens to populate it on an
        already-persisted record. The other tests in this class instantiate the
        wizard via `create({})`, which never exercises that view-driven fields_spec
        at all (default_get fills `line_ids` directly, bypassing the client's
        onchange round-trip). Driving the wizard through `Form` does exercise it:
        it opens a NewId record from the actual view and dispatches the real
        onchange, so if `line_ids` were ever removed from that view (breaking the
        fix in production) this test -- not just the others -- would catch it.

        `retention_line_ids` (a Many2many) can't be read past its length here:
        the onchange creates its lines as `Command.create` dicts that Form keeps
        as unsaved NewId placeholders, and `M2MProxy` has no `.edit()` (only
        One2many does) to read their fields without saving -- which would in
        turn require filling `retention_amount` by hand (see the mixed-selection
        test below for why), defeating the point of testing the view's onchange
        dispatch untouched. Exact invoice identity is already covered by
        `_get_context_invoices()` directly in the tests above; what this test
        adds is proof that the onchange resolves *something* through the real
        view-driven dispatch, i.e. that `line_ids` actually arrives.
        """
        invoice = self._create_invoice(1000.0)
        # Deliberately not `with Form(...) as wizard_form:` -- exiting that context
        # auto-saves, and saving here would need voucher_date/retention_ref (required
        # once is_retention is True) and a non-zero retention_amount on the line (see
        # the docstring above), none of which this test needs to fill in just to read
        # the onchange's result.
        wizard_form = Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move",
                active_ids=invoice.ids,
                # Set by account.move.action_register_payment (models/account_move.py)
                # for a real out_invoice; without it the view keeps is_retention invisible.
                default_is_out_invoice=True,
            )
        )
        wizard_form.is_retention = True
        self.assertEqual(
            len(wizard_form.retention_line_ids),
            1,
            "The onchange must have loaded exactly one retention line for the "
            "single invoice selected, proving line_ids reached it via the real view.",
        )

    def test_mixed_selection_only_loads_pending_invoice_retention(self):
        """
        Selecting a pending invoice together with an already fully-collected
        invoice of the same partner (e.g. from a list view) must only load
        retention lines for the invoice that is actually being paid. Before
        the fix, `_get_context_invoices` ignored the wizard's own line_ids
        filtering and returned both invoices, so the retention voucher ended
        up with lines belonging to an invoice that isn't being paid.
        """
        invoice_pending = self._create_invoice(1000.0)
        invoice_paid = self._create_invoice(500.0)
        self._pay_invoice_in_full(invoice_paid)
        self.assertEqual(invoice_paid.amount_residual, 0.0)
        self.assertNotEqual(invoice_pending.amount_residual, 0.0)

        # active_model="account.move.line" reproduces the real production path: the
        # "Register Payment" button on the invoice form delegates to
        # account.move.line.action_register_payment (see models/account_move.py),
        # which is the only path in this module that shows the retention checkbox --
        # not a plain list-view selection over account.move.
        wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move.line",
                active_ids=(invoice_pending + invoice_paid).line_ids.ids,
            )
            .create({})
        )

        # The base wizard's default_get already dropped the fully-reconciled
        # invoice's line (no residual left to pay).
        self.assertEqual(wizard._get_context_invoices(), invoice_pending)

        wizard.is_retention = True
        onchange_result = wizard._onchange_retention()
        # Customer (out_invoice) IVA retention lines aren't auto-computed by
        # account_retention_line._compute_retention_amount -- like their ISLR
        # counterpart, the amount is meant to be filled in by the user in the
        # UI before saving, so it must be set by hand here too.
        retention_line_commands = onchange_result["value"]["retention_line_ids"]
        for command in retention_line_commands:
            command[2]["retention_amount"] = command[2]["iva_amount"]
            command[2]["foreign_retention_amount"] = command[2]["foreign_iva_amount"]
        wizard.retention_line_ids = retention_line_commands
        wizard._onchange_retention_line_ids()

        payments = wizard._create_payments()
        retention = self.env["account.retention"].search(
            [("payment_ids", "in", payments.ids)]
        )
        self.assertTrue(retention, "The retention voucher must have been created.")
        self.assertEqual(
            retention.retention_line_ids.mapped("move_id"),
            invoice_pending,
            "The retention voucher must only contain lines from the invoice actually "
            "being paid, not from the already-collected one.",
        )
