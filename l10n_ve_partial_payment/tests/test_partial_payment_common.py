from odoo import fields
from odoo.tests import Form
from odoo.tests.common import new_test_user

from odoo.addons.l10n_ve_igtf.tests.test_igtf_common_partner_formal_VEF import (
    IGTFTestCommon,
)


class PartialPaymentTestCommon(IGTFTestCommon):
    """Shared fixtures for ``l10n_ve_partial_payment`` tests.

    Extends ``IGTFTestCommon`` (partner "formal", VEF/USD/EUR currencies
    with real rates, ``bank_journal_usd``/``bank_journal_bs``/
    ``bank_journal_eur``) with what this module's tests need on top:

    - The company flag (``partial_pay_from_outstanding``) turned on by
      default, since most tests exercise the feature enabled and only a
      couple flip it back off explicitly.
    - A USD bank journal WITHOUT IGTF (``bank_journal_usd_no_igtf``):
      ``IGTFTestCommon.bank_journal_usd`` has ``is_igtf: True``, which would
      add an IGTF line/amount to every payment made through it and
      contaminate the plain-amount assertions in tests that are not about
      IGTF at all (the multicurrency tests here care about exchange-rate
      proration, not IGTF).
    - Two users to exercise the ``group_partial_payment_apply`` gate:
      ``user_with_group`` (has it) and ``user_without_group`` (does not).

    No ``test_*`` methods live here on purpose -- this class only provides
    fixtures/helpers, so importing it elsewhere never risks duplicating the
    tests defined in this module's own test files.
    """

    def setUp(self):
        super().setUp()

        self.company.partial_pay_from_outstanding = True

        self.account_bank_usd_no_igtf = self.get_or_create_account(
            "1004", "asset_cash", "Cuenta de Banco USD (sin IGTF)"
        )

        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")

        self.pm_line_in_usd_no_igtf = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound USD (sin IGTF)",
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank_usd_no_igtf.id,
            }
        )
        self.pm_line_out_usd_no_igtf = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound USD (sin IGTF)",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank_usd_no_igtf.id,
            }
        )

        self.bank_journal_usd_no_igtf = self.Journal.create(
            {
                "name": "Banco USD (sin IGTF)",
                "code": "BNKUN",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
                "is_igtf": False,
                "default_account_id": self.account_bank_usd_no_igtf.id,
                "inbound_payment_method_line_ids": [
                    (6, 0, self.pm_line_in_usd_no_igtf.ids)
                ],
                "outbound_payment_method_line_ids": [
                    (6, 0, self.pm_line_out_usd_no_igtf.ids)
                ],
            }
        )
        self.pm_line_in_usd_no_igtf.journal_id = self.bank_journal_usd_no_igtf.id
        self.pm_line_out_usd_no_igtf.journal_id = self.bank_journal_usd_no_igtf.id

        self.user_with_group = new_test_user(
            self.env,
            login="partial_ok",
            email="partial.ok@example.com",
            groups="account.group_account_invoice",
        )
        self.user_with_group.group_ids |= self.env.ref(
            "l10n_ve_partial_payment.group_partial_payment_apply"
        )

        self.user_without_group = new_test_user(
            self.env,
            login="partial_no",
            email="partial.no@example.com",
            groups="account.group_account_invoice",
        )

    def _apply_partial(self, invoice, line, amount, user=None):
        """Call ``js_assign_outstanding_line`` routed through the partial-amount context key.

        Parameters
        ----------
        invoice : account.move
            The invoice the outstanding line is being applied against.
        line : account.move.line
            The outstanding credit/debit line selected from the popover.
        amount : float
            Requested partial amount, in the invoice's currency.
        user : res.users, optional
            Acting user; defaults to ``self.user_with_group``.
        """
        # `invoice` was built via `Form` (see `IGTFTestCommon._create_invoice_*`),
        # whose `default_journal_id`/`default_move_type` context keys survive
        # on the saved record's env. Merging our key with `with_context(**kw)`
        # would keep those leaking in, and `_create_advance_payment_move`
        # (l10n_ve_igtf) creates its cross-entry move without an explicit
        # `journal_id`, so it silently inherits `default_journal_id` (a SALE
        # journal) for a move that isn't a sale document -- Odoo's own
        # `_check_journal_move_type` then rejects it. Resetting the context
        # first (dict positional arg replaces instead of merging) avoids this,
        # matching the pattern `l10n_ve_igtf_note_debit`'s tests already use
        # (`invoice.with_context({})...`).
        return (
            invoice.with_user(user or self.user_with_group)
            .with_context({"l10n_ve_partial_paid_amount": amount})
            .js_assign_outstanding_line(line.id)
        )

    def _outstanding_line_for_payment(self, payment, account):
        """Return the uncollected/unpaid credit line of ``payment`` on ``account``."""
        return payment.move_id.line_ids.filtered(
            lambda l: l.account_id == account and l.credit > 0
        )

    def _create_advance_payment(self, journal, amount, partner_type="customer"):
        """Create a posted advance payment (``default_is_advance_payment=True``).

        Mirrors ``l10n_ve_igtf_note_debit``'s helper of the same name: the
        ``default_is_advance_payment`` context key is what makes
        ``account.payment`` set ``is_advance_payment=True``, which is the
        predicate ``account_move._is_advance_outstanding_line`` (and
        ``l10n_ve_igtf``'s own ``js_assign_outstanding_line``) uses to route
        through the advance-move branch.
        """
        payment_type = "inbound" if partner_type == "customer" else "outbound"
        context = {
            "default_payment_type": payment_type,
            "default_partner_type": partner_type,
            "search_default_inbound_filter": 1,
            "default_move_journal_types": ("bank", "cash"),
            "display_account_trust": True,
            "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = journal
            pay_form.amount = amount
        payment = pay_form.save()
        payment.action_post()
        return payment

    def _create_plain_payment(self, journal, amount, partner_type="customer"):
        """Create a posted plain payment (no ``default_is_advance_payment``).

        Replicates a loose payment (created apart, with no origin invoice,
        not explicitly flagged as an "advance") whose outstanding line later
        gets applied by hand from a payment widget -- exercises the
        non-advance branch of ``js_assign_outstanding_line``.
        """
        payment_type = "inbound" if partner_type == "customer" else "outbound"
        payment = self.env["account.payment"].create(
            {
                "payment_type": payment_type,
                "partner_type": partner_type,
                "partner_id": self.partner.id,
                "amount": amount,
                "journal_id": journal.id,
            }
        )
        payment.action_post()
        return payment

    def _create_invoice_in_vef(self, amount, date=None):
        """Create+post a VEF vendor bill (``in_invoice``) for ``amount``.

        Mirrors ``IGTFTestCommon._create_invoice_vef`` but for the payable
        side, needed only by the vendor-invoice partial-application test
        (point 13): that test exercises the negative-residual ``sign``
        branch of ``account_move_line._prepare_reconciliation_amls``, which
        the customer-side helpers never reach.
        """
        purchase_journal = self.Journal.search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        if not purchase_journal:
            purchase_journal = self.Journal.create(
                {
                    "name": "Diario Compra",
                    "type": "purchase",
                    "code": "PURC",
                    "company_id": self.company.id,
                    "currency_id": self.currency_vef.id,
                }
            )

        with Form(
            self.env["account.move"].with_context(
                default_move_type="in_invoice", default_journal_id=purchase_journal
            )
        ) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_vef
            inv_form.save()

        inv = inv_form.save()
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount

        return inv_form_edit.save()
