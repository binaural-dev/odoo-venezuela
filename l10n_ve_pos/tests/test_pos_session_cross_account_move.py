"""Cross-account clearing move tests (transitoria -> banco).

Verifies the reactivated cruce automatico in ``pos_session.py``:
``_validate_cross_move`` / ``_line_vals_move_cross_incoming`` /
``_line_vals_move_cross_outgoing`` / ``_create_cross_move`` (split path) and
``_create_combine_account_payment`` / ``_create_cross_move_payment`` /
``_line_vals_move_cross_payment_incoming`` (combine path).

Spec: ``openspec/changes/l10n-ve-pos-cross-account-move/specs/pos-cross-account-move/spec.md``
"""

from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "cross_move")
class TestPosSessionCrossAccountMove(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # A distinct "real bank" account/journal, separate from the
        # payment methods' own outstanding_account_id (account_bank), so
        # the cross move visibly moves value between two different
        # accounts instead of a same-account wash.
        cls.account_real_bank = cls.env["account.account"].create(
            {
                "name": "C Real Bank",
                "code": "110001C",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        manual_in = cls.env.ref("account.account_payment_method_manual_in")
        manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.real_bank_journal = cls.env["account.journal"].create(
            {
                "name": "C Real Bank Journal",
                "type": "bank",
                "code": "RBJC",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_real_bank.id,
                "inbound_payment_method_line_ids": [
                    (0, 0, {
                        "payment_method_id": manual_in.id,
                        "payment_account_id": cls.account_real_bank.id,
                    })
                ],
                "outbound_payment_method_line_ids": [
                    (0, 0, {
                        "payment_method_id": manual_out.id,
                        "payment_account_id": cls.account_real_bank.id,
                    })
                ],
            }
        )
        cls.cross_account_journal = cls.env["account.journal"].create(
            {
                "name": "C Cross Adjustment Journal",
                "type": "general",
                "code": "CAJC",
                "company_id": cls.company.id,
            }
        )

    def _configure_cross(self, method, *, cross_account_journal=True, cross_journal=True, apply=True):
        vals = {"apply_one_cross_move": apply}
        if cross_account_journal:
            vals["cross_account_journal"] = self.cross_account_journal.id
        if cross_journal:
            vals["cross_journal"] = self.real_bank_journal.id
        method.write(vals)

    def _cross_moves(self):
        return self.env["account.move"].search(
            [("journal_id", "=", self.cross_account_journal.id), ("company_id", "=", self.company.id)]
        )

    def _new_session(self):
        return self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    # ------------------------------------------------------------------
    def test_cross_move_split_incoming(self):
        """Pago split entrante con apply_one_cross_move=True crea el cruce."""
        self._configure_cross(self.split_bank_method)
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=36.5,
            name="OL/CROSS/SPLIT-IN",
        )
        payment = order.payment_ids[0]

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1, "debe crearse exactamente un cruce")
        move = moves[0]
        self.assertEqual(move.state, "draft", "el cruce nunca se postea automaticamente")

        real_bank_line = move.line_ids.filtered(
            lambda l: l.account_id == self.account_real_bank
        )
        transitory_line = move.line_ids.filtered(
            lambda l: l.account_id == self.split_bank_method.outstanding_account_id
        )
        self.assertTrue(real_bank_line, "debe haber una linea sobre la cuenta real de banco")
        self.assertTrue(transitory_line, "debe haber una linea sobre la cuenta transitoria")

        self.assertAlmostEqual(real_bank_line.debit, payment.amount, places=2)
        self.assertAlmostEqual(real_bank_line.foreign_debit, payment.foreign_amount, places=2)
        self.assertTrue(real_bank_line.not_foreign_recalculate)

        self.assertAlmostEqual(transitory_line.credit, payment.amount, places=2)
        self.assertAlmostEqual(transitory_line.foreign_credit, payment.foreign_amount, places=2)
        self.assertTrue(transitory_line.not_foreign_recalculate)

    def test_cross_move_split_outgoing_refund(self):
        """Pago split saliente (reembolso, amount<0) crea el cruce espejo."""
        self._configure_cross(self.split_bank_method)
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=-30.0,
            tax_amount=-4.0,
            foreign_rate=36.5,
            name="OL/CROSS/SPLIT-OUT",
        )
        payment = order.payment_ids[0]

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1)
        move = moves[0]
        self.assertEqual(move.state, "draft")

        real_bank_line = move.line_ids.filtered(
            lambda l: l.account_id == self.account_real_bank
        )
        transitory_line = move.line_ids.filtered(
            lambda l: l.account_id == self.split_bank_method.outstanding_account_id
        )
        self.assertTrue(real_bank_line)
        self.assertTrue(transitory_line)

        # Espejo del caso entrante: se acredita la cuenta real y se debita
        # la transitoria, en magnitudes absolutas.
        self.assertAlmostEqual(real_bank_line.credit, abs(payment.amount), places=2)
        self.assertAlmostEqual(real_bank_line.foreign_credit, abs(payment.foreign_amount), places=2)
        self.assertAlmostEqual(transitory_line.debit, abs(payment.amount), places=2)
        self.assertAlmostEqual(transitory_line.foreign_debit, abs(payment.foreign_amount), places=2)

    def test_cross_move_combine_incoming(self):
        """Pago combine entrante con apply_one_cross_move=True crea el cruce."""
        self._configure_cross(self.combined_bank_method)
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session,
            method=self.combined_bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=36.5,
            name="OL/CROSS/COMBINE-IN",
        )
        payment = order.payment_ids[0]
        amounts = {
            "amount": payment.amount,
            "amount_converted": payment.amount,
            "foreign_amount": payment.foreign_amount,
        }

        session._create_combine_account_payment(self.combined_bank_method, amounts, diff_amount=0)

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1)
        move = moves[0]
        self.assertEqual(move.state, "draft")

        real_bank_line = move.line_ids.filtered(
            lambda l: l.account_id == self.account_real_bank
        )
        transitory_line = move.line_ids.filtered(
            lambda l: l.account_id == self.combined_bank_method.outstanding_account_id
        )
        self.assertTrue(real_bank_line)
        self.assertTrue(transitory_line)
        self.assertAlmostEqual(real_bank_line.debit, payment.amount, places=2)
        self.assertAlmostEqual(real_bank_line.foreign_debit, payment.foreign_amount, places=2)
        self.assertAlmostEqual(transitory_line.credit, payment.amount, places=2)
        self.assertAlmostEqual(transitory_line.foreign_credit, payment.foreign_amount, places=2)

    def test_no_cross_move_when_flag_disabled(self):
        """apply_one_cross_move=False (default) no crea ningun cruce."""
        self._configure_cross(self.split_bank_method, apply=False)
        session = self._new_session().with_company(self.company)
        self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            name="OL/CROSS/NOFLAG",
        )

        session._validate_cross_move()

        self.assertEqual(len(self._cross_moves()), 0)

    def test_no_cross_move_when_journal_missing(self):
        """apply_one_cross_move=True pero falta un journal: no crea nada ni rompe."""
        for missing in ("cross_account_journal", "cross_journal"):
            with self.subTest(missing=missing):
                # Odoo bloquea escribir sobre un pos.payment.method mientras
                # tenga una sesion abierta -- configurar ANTES de abrir la
                # sesion de esta iteracion.
                self.split_bank_method.write(
                    {"apply_one_cross_move": False, "cross_account_journal": False, "cross_journal": False}
                )
                self._configure_cross(
                    self.split_bank_method,
                    cross_account_journal=(missing != "cross_account_journal"),
                    cross_journal=(missing != "cross_journal"),
                )
                session = self._new_session().with_company(self.company)
                self._create_paid_order(
                    session,
                    method=self.split_bank_method,
                    amount=58.0,
                    tax_amount=8.0,
                    name=f"OL/CROSS/MISSING-{missing}",
                )

                session._validate_cross_move()

                self.assertEqual(len(self._cross_moves()), 0)

                # Liberar la sesion (sin pasar por el cierre real) para que
                # la siguiente iteracion pueda reconfigurar el metodo y abrir
                # una sesion nueva sobre el mismo pos.config.
                session.write({"state": "closed"})

    def test_cross_move_cash_method_falls_back_to_default_pos_receivable_account(self):
        """Metodo de pago CASH sin outstanding_account_id usa el fallback nativo.

        ``outstanding_account_id`` es invisible/no editable en la UI nativa
        para metodos que no son ``bank`` (ver
        ``point_of_sale/views/pos_payment_method_views.xml:24``,
        ``invisible="type != 'bank'"``) -- un metodo cash SIEMPRE lo tiene
        vacio. Sin el fallback en ``_get_cross_transitory_account``, la linea
        de cruce se creaba con ``account_id = NULL`` y Postgres rechazaba el
        insert (``account_move_line_check_accountable_required_fields``).

        ``split_cash_method`` (de ``TestPosSessionAccountingBase``) nunca
        recibe ``outstanding_account_id`` en su fixture -- exactamente el
        estado real de un metodo cash en produccion.
        """
        self.assertFalse(
            self.split_cash_method.outstanding_account_id,
            "fixture must mirror production: cash methods never have outstanding_account_id",
        )
        self._configure_cross(self.split_cash_method)
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session,
            method=self.split_cash_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=36.5,
            name="OL/CROSS/CASH-FALLBACK",
        )
        payment = order.payment_ids[0]

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1, "debe crearse el cruce usando la cuenta de fallback")
        move = moves[0]
        self.assertEqual(move.state, "draft")

        transitory_line = move.line_ids.filtered(
            lambda l: l.account_id == self.account_pos_receivable
        )
        self.assertTrue(
            transitory_line,
            "la pata transitoria debe caer en account_default_pos_receivable_account_id",
        )
        self.assertAlmostEqual(transitory_line.credit, payment.amount, places=2)
        self.assertAlmostEqual(transitory_line.foreign_credit, payment.foreign_amount, places=2)
        self.assertTrue(transitory_line.not_foreign_recalculate)

    def test_cross_move_amount_currency_uses_configured_foreign_currency_not_hardcoded_id(self):
        """Regresion del bug `currency == 3`: usa self.foreign_currency_id, no un id fijo.

        Configura el cross_journal con la moneda de la COMPANIA (no la
        foranea) explicitamente. Si el codigo comparara contra un id
        hardcodeado en vez de contra `self.foreign_currency_id`, esta
        distincion se perderia silenciosamente.
        """
        self._configure_cross(self.split_bank_method)
        self.real_bank_journal.currency_id = self.company.currency_id
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=36.5,
            name="OL/CROSS/CURRENCY",
        )
        payment = order.payment_ids[0]

        session._validate_cross_move()

        move = self._cross_moves()
        self.assertEqual(len(move), 1)
        real_bank_line = move.line_ids.filtered(
            lambda l: l.account_id == self.account_real_bank
        )
        # La linea de la cuenta real vive en la moneda de la compania
        # (no la foranea): amount_currency debe ser payment.amount, no
        # payment.foreign_amount.
        self.assertAlmostEqual(real_bank_line.amount_currency, payment.amount, places=2)
        self.assertNotAlmostEqual(
            real_bank_line.amount_currency, payment.foreign_amount, places=2
        )
