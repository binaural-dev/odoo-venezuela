"""Slice C2: Session Accounting Move Creation TDD tests.

Verifies that ``l10n_ve_pos`` C2 overrides adapt to the Odoo 19 return types
and preserve the Venezuelan ``foreign_rate``, ``foreign_inverse_rate``,
``foreign_debit`` and ``foreign_credit`` writes.

Scope of THIS batch (Slice C2.1 only):
- ``_create_split_account_payment`` (``models/pos_session.py``): Odoo 19
  returns an ``account.move.line`` recordset, not a move. The pre-C2
  l10n_ve_pos override accessed ``res.move_id.payment_id``, which raises
  ``AttributeError`` in Odoo 19 (the field on ``account.move`` was renamed
  to ``origin_payment_id``).

The remaining C2 sub-slices (C2.2 → C2.5) are tracked as ``skip`` for the
next batch — they need their own targeted fixes and are dependency-ready
once C2.1 lands. See ``tasks.md`` §"Slice C2".

Spec: ``openspec/changes/l10n-ve-pos-migration-plan/specs/pos-odoo19-session-accounting/spec.md``
Doc:   ``.../specs/pos-odoo19-session-accounting/key-map.md``
Native Odoo 19 references:
- ``/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1145-1170``
  (``_create_split_account_payment`` returns ``account.move.line``).
- ``/home/binaural19/odoo/addons/account/models/account_move.py:206``
  (``account.move.origin_payment_id`` replaces the legacy ``payment_id``).
"""

import unittest

from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "slice_c2")
class TestPosSessionAccountingMoveCreation(TestPosSessionAccountingBase):
    """Spec: ``pos-odoo19-session-accounting/spec.md`` (C2.1 landed; C2.2–C2.5 pending).

    Odoo 19 ``_create_split_account_payment`` returns an ``account.move.line``
    recordset (the receivable line), not a move. The pre-C2 l10n_ve_pos
    override did ``res.move_id.payment_id`` which is no longer valid.

    The test layer is **Unit** (Odoo ORM in-process): we exercise the method
    directly on a paid split-bank payment without running the full
    ``_create_account_move`` pipeline — this isolates the C2.1 contract from
    C2.2 / C2.3 / C2.4 (which cover the pipeline branches and are pending
    for the next batch).
    """

    # ==================================================================
    # C2.1 — ``_create_split_account_payment`` (HIGH RISK)
    # ------------------------------------------------------------------
    # Odoo 19 returns an ``account.move.line`` recordset, not a move.
    # The pre-C2 l10n_ve_pos override did ``res.move_id.payment_id``,
    # which raises ``AttributeError`` in Odoo 19 (the field on the move
    # is ``origin_payment_id``, and the line recordset has no
    # ``move_id.payment_id`` chain at all).
    # ==================================================================
    def test_create_split_account_payment_writes_foreign_fields_on_receivable_and_move(self):
        """C2.1 — split account payment preserves Venezuelan fields.

        The method is exercised in isolation (not via ``_create_account_move``)
        so the C2.1 regression surfaces here without depending on the C2.2/C2.3
        pipeline branches.
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        order = self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            name="OL/C2.1/SPLIT",
        )
        payment = order.payment_ids[0]
        amounts = {
            "amount": payment.amount,
            "amount_converted": payment.amount,
            "foreign_amount": payment.foreign_amount,
        }

        # Set a distinctive foreign_rate on the config so we can assert it
        # propagated onto the created ``account.payment``. This forces
        # triangulation against C2's write contract.
        self.config.write({"foreign_rate": 42.5, "foreign_inverse_rate": 1 / 42.5})

        # ACT — the pre-C2 l10n_ve_pos override crashes here because it
        # does ``account_payment = res.move_id.payment_id`` on the Odoo 19
        # return value (an ``account.move.line`` recordset whose parent
        # move exposes ``origin_payment_id``, not ``payment_id``).
        #
        # ``.with_company()`` propagates ``env.company = test_company`` to
        # both session AND payment; the Odoo 19 super calls
        # ``_find_accounting_partner(payment.partner_id)`` and reads
        # ``property_account_receivable_id`` in the resulting partner's
        # env — that env inherits from ``payment.partner_id``'s env, so
        # payment MUST be rebound too.
        receivable_lines = session.with_company(
            self.company
        )._create_split_account_payment(
            payment.with_company(self.company), amounts
        )

        # Odoo 19 return-type contract.
        self.assertTrue(
            receivable_lines,
            "_create_split_account_payment must return a non-empty recordset",
        )
        self.assertEqual(
            receivable_lines._name,
            "account.move.line",
            "Odoo 19 contract: _create_split_account_payment returns account.move.line",
        )

        # The receivable line must carry the Venezuelan foreign_credit.
        self.assertGreater(receivable_lines[0].credit, 0)
        self.assertAlmostEqual(
            receivable_lines[0].foreign_credit,
            abs(payment.foreign_amount),
            places=2,
            msg="receivable line must carry the Venezuelan foreign_credit",
        )
        self.assertTrue(
            receivable_lines[0].not_foreign_recalculate,
            "receivable line must have not_foreign_recalculate=True",
        )

        # The originating ``account.payment`` (Odoo 19: reached via
        # ``move.origin_payment_id``) must carry the config's foreign_rate
        # / foreign_inverse_rate — this is the writeback the pre-C2
        # override attempted through the now-broken ``payment_id`` chain.
        origin_payment = receivable_lines.move_id.origin_payment_id
        self.assertTrue(
            origin_payment,
            "Odoo 19 contract: account.move exposes origin_payment_id (not payment_id)",
        )
        self.assertAlmostEqual(
            origin_payment.foreign_rate,
            self.config.foreign_rate,
            places=4,
            msg="origin_payment must carry config.foreign_rate",
        )
        self.assertAlmostEqual(
            origin_payment.foreign_inverse_rate,
            self.config.foreign_inverse_rate,
            places=4,
            msg="origin_payment must carry config.foreign_inverse_rate",
        )

        # Every line of the originating move must carry the matching
        # ``foreign_debit`` / ``foreign_credit`` write — this is the
        # additive Venezuelan contract preserved across the C2 refactor.
        for line in receivable_lines.move_id.line_ids:
            if line.credit > 0:
                self.assertAlmostEqual(
                    line.foreign_credit,
                    abs(payment.foreign_amount),
                    places=2,
                    msg="credit line must carry the Venezuelan foreign_credit",
                )
                self.assertTrue(line.not_foreign_recalculate)
            if line.debit > 0:
                self.assertAlmostEqual(
                    line.foreign_debit,
                    abs(payment.foreign_amount),
                    places=2,
                    msg="debit line must carry the Venezuelan foreign_debit",
                )
                self.assertTrue(line.not_foreign_recalculate)

    def test_create_split_account_payment_returns_empty_recordset_when_journal_missing(self):
        """C2.1 triangulation — safe short-circuit when payment method has no journal.

        Odoo 19 ``_create_split_account_payment`` returns
        ``self.env['account.move.line']`` (empty recordset) if the payment
        method has no journal (native line 1147-1148). The l10n_ve_pos
        override must not crash on the empty recordset and must not attempt
        to write foreign fields on non-existent records — this is the
        second RED path guarding against the ``payment_id`` chain (the
        legacy chain would raise ``AttributeError`` on the empty move too).
        """
        # Build a payment method with no journal (Odoo 19 early-return path)
        # and attach it to the config so ``_check_payment_method_id`` is
        # satisfied when the payment references it.
        method_no_journal = self.env["pos.payment.method"].create(
            {
                "name": "C2.1 No Journal Method",
                "is_cash_count": False,
                "split_transactions": True,
                "company_id": self.company.id,
            }
        )
        method_no_journal.write({"is_foreign_currency": True})
        self.config.write(
            {"payment_method_ids": [(4, method_no_journal.id)]}
        )

        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        order = self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            name="OL/C2.1/NOJRN",
        )
        # Swap the payment's method to the journal-less one in place.
        payment = order.payment_ids[0]
        payment.payment_method_id = method_no_journal
        amounts = {
            "amount": payment.amount,
            "amount_converted": payment.amount,
            "foreign_amount": payment.foreign_amount,
        }

        result = session.with_company(self.company)._create_split_account_payment(
            payment.with_company(self.company), amounts
        )
        self.assertEqual(
            result._name,
            "account.move.line",
            "Odoo 19 early-return contract: empty recordset of account.move.line",
        )
        self.assertFalse(result, "no-journal path must return an EMPTY recordset")

    # ==================================================================
    # C2.2 → C2.5: pending next batch
    # ------------------------------------------------------------------
    # These tests were drafted alongside C2.1 but require dedicated
    # implementation work (bank/cash pipeline branches, invoice
    # receivables, ``pos.payment._create_payment_moves``). They are
    # skipped here so this batch stays scoped to the critical
    # ``_create_split_account_payment`` return-type mismatch.
    # ==================================================================
    @unittest.skip("Slice C2.2 — pending next batch (bank payment moves)")
    def test_create_bank_payment_moves_writes_foreign_fields_on_receivable_lines(self):
        pass

    @unittest.skip("Slice C2.3 — pending next batch (cash statement lines)")
    def test_create_cash_statement_lines_writes_foreign_fields_on_cash_receivable(self):
        pass

    @unittest.skip("Slice C2.4 — pending next batch (invoice receivable lines)")
    def test_create_invoice_receivable_lines_writes_foreign_fields_on_invoiced_receivable(self):
        pass

    @unittest.skip("Slice C2.5 — pending next batch (pos.payment._create_payment_moves)")
    def test_create_payment_moves_writes_foreign_fields_on_invoiced_payment(self):
        pass
