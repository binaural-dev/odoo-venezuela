"""Cross-account clearing move tests (transitoria -> banco/caja real).

Verifies the cruce automatico in ``pos_session.py``: ``_validate_cross_move``
(single entry point for both granularities), ``_is_cross_move_eligible``,
``_get_cross_transitory_account``, ``_line_vals_move_cross_incoming`` /
``_line_vals_move_cross_outgoing``, ``_create_cross_move_for`` and
``_create_cross_move``.

Spec: ``openspec/changes/l10n-ve-pos-cross-move-by-split-transactions/specs/pos-cross-account-move/spec.md``
"""

from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "cross_move")
class TestPosSessionCrossAccountMove(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # A distinct "real bank" account/journal, separate from the
        # payment methods' own transitory account (account_bank for bank
        # methods, account_cash for cash ones), so the cross move visibly
        # moves value between two different accounts instead of a
        # same-account wash.
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

    def _configure_cross(self, method, *, cross_account_journal=True, cross_journal=True):
        """Wire up a payment method for the cross move.

        ``is_foreign_currency`` is the only switch that arms the flow (the
        base fixture already sets it on all four methods), so this helper
        only has to fill in the two journals. Passing either flag as False
        leaves that journal empty, which is the "incomplete configuration"
        case the flow must skip in silence.
        """
        vals = {}
        vals["cross_account_journal"] = self.cross_account_journal.id if cross_account_journal else False
        vals["cross_journal"] = self.real_bank_journal.id if cross_journal else False
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

    def _legs(self, move, transitory_account):
        """Split a cross move into (real-account leg, transitory leg)."""
        real_leg = move.line_ids.filtered(lambda l: l.account_id == self.account_real_bank)
        transitory_leg = move.line_ids.filtered(lambda l: l.account_id == transitory_account)
        self.assertTrue(real_leg, "debe haber una linea sobre la cuenta real")
        self.assertTrue(transitory_leg, "debe haber una linea sobre la cuenta transitoria")
        return real_leg, transitory_leg

    # ------------------------------------------------------------------
    # Granularidad: split_transactions decide cuantos asientos se crean
    # ------------------------------------------------------------------
    def test_split_method_creates_one_move_per_payment(self):
        """split_transactions=True -> un asiento por cada pago."""
        self._configure_cross(self.split_bank_method)
        session = self._new_session().with_company(self.company)
        for i, amount in enumerate((58.0, 42.0, 25.0)):
            self._create_paid_order(
                session,
                method=self.split_bank_method,
                amount=amount,
                tax_amount=8.0,
                foreign_rate=36.5,
                name=f"OL/CROSS/SPLIT-{i}",
            )

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 3, "split: un asiento por cada uno de los 3 pagos")
        self.assertEqual(
            sorted(moves.mapped(lambda m: sum(m.line_ids.mapped("debit")))),
            [25.0, 42.0, 58.0],
            "cada asiento lleva el importe de su propio pago",
        )

    def test_combine_method_creates_one_move_per_session(self):
        """split_transactions=False -> UN solo asiento, neteando los pagos.

        Este es el caso que reproducia el bug reportado: el metodo combine
        recibia un asiento agregado desde ``_create_combine_account_payment``
        MAS uno por pago desde ``_validate_cross_move``, que no filtraba por
        ``split_transactions``. Con 3 pagos se creaban 4 asientos y activar o
        no "Identificar cliente" no cambiaba nada.
        """
        self._configure_cross(self.combined_bank_method)
        session = self._new_session().with_company(self.company)
        for i, amount in enumerate((58.0, 42.0, 25.0)):
            self._create_paid_order(
                session,
                method=self.combined_bank_method,
                amount=amount,
                tax_amount=8.0,
                foreign_rate=36.5,
                name=f"OL/CROSS/COMBINE-{i}",
            )

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1, "combine: un unico asiento por metodo/sesion")
        real_leg, transitory_leg = self._legs(
            moves, self.combined_bank_method.outstanding_account_id
        )
        self.assertAlmostEqual(real_leg.debit, 125.0, places=2, msg="58 + 42 + 25")
        self.assertAlmostEqual(transitory_leg.credit, 125.0, places=2)

    def test_combine_and_split_methods_coexist_in_one_session(self):
        """Cada metodo aplica su propia granularidad en la misma sesion."""
        self._configure_cross(self.combined_bank_method)
        self._configure_cross(self.split_cash_method)
        session = self._new_session().with_company(self.company)
        for i in range(2):
            self._create_paid_order(
                session,
                method=self.combined_bank_method,
                amount=50.0,
                tax_amount=8.0,
                name=f"OL/CROSS/MIX-BANK-{i}",
            )
            self._create_paid_order(
                session,
                method=self.split_cash_method,
                amount=30.0,
                tax_amount=4.0,
                name=f"OL/CROSS/MIX-CASH-{i}",
            )

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(
            len(moves), 3, "1 asiento del metodo combine + 2 del metodo split"
        )
        # El metodo bank vacia account_bank (su outstanding); el cash vacia
        # account_cash (la cuenta de su diario). Contar por cuenta transitoria
        # separa las dos granularidades dentro de la misma sesion.
        bank_moves = moves.filtered(
            lambda m: self.account_bank in m.line_ids.account_id
        )
        cash_moves = moves.filtered(
            lambda m: self.account_cash in m.line_ids.account_id
        )
        self.assertEqual(len(bank_moves), 1, "combine: los 2 pagos bank en un solo asiento")
        self.assertEqual(len(cash_moves), 2, "split: un asiento por cada pago cash")
        self.assertAlmostEqual(
            sum(bank_moves.line_ids.mapped("debit")), 100.0, places=2, msg="50 + 50"
        )

    # ------------------------------------------------------------------
    # Direccion del asiento (signo)
    # ------------------------------------------------------------------
    def test_split_outgoing_refund(self):
        """Pago split saliente (amount<0) crea el cruce espejo."""
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
        self.assertEqual(moves.state, "draft")
        real_leg, transitory_leg = self._legs(
            moves, self.split_bank_method.outstanding_account_id
        )
        # Espejo del caso entrante: se acredita la cuenta real y se debita
        # la transitoria, en magnitudes absolutas.
        self.assertAlmostEqual(real_leg.credit, abs(payment.amount), places=2)
        self.assertAlmostEqual(real_leg.foreign_credit, abs(payment.foreign_amount), places=2)
        self.assertAlmostEqual(transitory_leg.debit, abs(payment.amount), places=2)
        self.assertAlmostEqual(transitory_leg.foreign_debit, abs(payment.foreign_amount), places=2)

    def test_combine_net_negative_uses_outgoing_branch(self):
        """Combine cuyo neto queda negativo produce UN asiento saliente.

        La ruta combine legacy solo tenia rama entrante. Al netear los pagos
        del metodo, un neto negativo (mas devoluciones que ventas) es
        alcanzable y debe salir por la rama espejo.
        """
        self._configure_cross(self.combined_bank_method)
        session = self._new_session().with_company(self.company)
        self._create_paid_order(
            session,
            method=self.combined_bank_method,
            amount=40.0,
            tax_amount=8.0,
            name="OL/CROSS/NET-NEG-SALE",
        )
        self._create_paid_order(
            session,
            method=self.combined_bank_method,
            amount=-100.0,
            tax_amount=-8.0,
            name="OL/CROSS/NET-NEG-REFUND",
        )

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1)
        real_leg, transitory_leg = self._legs(
            moves, self.combined_bank_method.outstanding_account_id
        )
        self.assertAlmostEqual(real_leg.credit, 60.0, places=2, msg="|40 - 100|")
        self.assertAlmostEqual(transitory_leg.debit, 60.0, places=2)

    def test_combine_net_zero_creates_nothing(self):
        """Combine cuyo neto es cero no crea asiento: no hay nada que cruzar."""
        self._configure_cross(self.combined_bank_method)
        session = self._new_session().with_company(self.company)
        self._create_paid_order(
            session,
            method=self.combined_bank_method,
            amount=58.0,
            tax_amount=8.0,
            name="OL/CROSS/NET-ZERO-SALE",
        )
        self._create_paid_order(
            session,
            method=self.combined_bank_method,
            amount=-58.0,
            tax_amount=-8.0,
            name="OL/CROSS/NET-ZERO-REFUND",
        )

        session._validate_cross_move()

        self.assertEqual(len(self._cross_moves()), 0)

    # ------------------------------------------------------------------
    # Cuenta transitoria segun el tipo de metodo
    # ------------------------------------------------------------------
    def test_bank_method_drains_outstanding_account(self):
        """Metodo bank: la pata transitoria es su outstanding_account_id."""
        self._configure_cross(self.split_bank_method)
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=36.5,
            name="OL/CROSS/BANK-IN",
        )
        payment = order.payment_ids[0]

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.state, "draft", "el cruce nunca se postea automaticamente")
        real_leg, transitory_leg = self._legs(moves, self.account_bank)
        self.assertEqual(
            self.split_bank_method.outstanding_account_id,
            self.account_bank,
            "fixture: el metodo bank si tiene outstanding_account_id",
        )
        self.assertAlmostEqual(real_leg.debit, payment.amount, places=2)
        self.assertAlmostEqual(real_leg.foreign_debit, payment.foreign_amount, places=2)
        self.assertTrue(real_leg.not_foreign_recalculate)
        self.assertAlmostEqual(transitory_leg.credit, payment.amount, places=2)
        self.assertAlmostEqual(transitory_leg.foreign_credit, payment.foreign_amount, places=2)
        self.assertTrue(transitory_leg.not_foreign_recalculate)

    def test_cash_method_drains_its_journal_account_not_pos_receivable(self):
        """Metodo cash: la pata transitoria es la cuenta de su diario de caja.

        ``outstanding_account_id`` es invisible en la UI nativa para metodos
        que no son ``bank`` (``point_of_sale/views/pos_payment_method_views.xml:24``,
        ``invisible="type != 'bank'"``) -- un metodo cash SIEMPRE lo tiene
        vacio, porque Odoo enruta el efectivo directo al diario.

        El statement line nativo debita ``journal_id.default_account_id`` y
        acredita la POS receivable (``_get_combine_statement_line_vals``,
        nativo linea 1452), asi que al cerrar la sesion la POS receivable
        queda saldada en cero y el dinero queda en la cuenta del diario.
        Vaciar la POS receivable descuadraria una cuenta ya en cero sin
        tocar el efectivo que se pretendia mover.
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
            name="OL/CROSS/CASH",
        )
        payment = order.payment_ids[0]

        session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1)
        self.assertEqual(
            self.split_cash_method.journal_id.default_account_id,
            self.account_cash,
            "fixture: el diario de caja apunta a account_cash",
        )
        _real_leg, transitory_leg = self._legs(moves, self.account_cash)
        self.assertAlmostEqual(transitory_leg.credit, payment.amount, places=2)
        self.assertAlmostEqual(transitory_leg.foreign_credit, payment.foreign_amount, places=2)
        self.assertTrue(transitory_leg.not_foreign_recalculate)
        self.assertFalse(
            moves.line_ids.filtered(lambda l: l.account_id == self.account_pos_receivable),
            "la POS receivable ya quedo saldada por el statement line nativo: "
            "el cruce no debe tocarla",
        )

    # ------------------------------------------------------------------
    # Elegibilidad
    # ------------------------------------------------------------------
    def test_no_cross_move_when_not_foreign_currency(self):
        """is_foreign_currency=False no crea cruce aunque tenga los diarios.

        ``is_foreign_currency`` es el unico interruptor del flujo desde que
        se retiro ``apply_one_cross_move``.
        """
        self._configure_cross(self.split_bank_method)
        self.split_bank_method.write({"is_foreign_currency": False})
        session = self._new_session().with_company(self.company)
        self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            name="OL/CROSS/NOT-FOREIGN",
        )

        session._validate_cross_move()

        self.assertEqual(len(self._cross_moves()), 0)

    def test_no_cross_move_when_journal_missing(self):
        """Falta un diario de cruce: no crea nada ni rompe."""
        for missing in ("cross_account_journal", "cross_journal"):
            with self.subTest(missing=missing):
                # Odoo bloquea escribir sobre un pos.payment.method mientras
                # tenga una sesion abierta -- configurar ANTES de abrir la
                # sesion de esta iteracion.
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

    def test_pay_later_method_is_not_eligible(self):
        """Un metodo pay_later nunca cruza: no hay transitoria que vaciar.

        El guard no es redundante: un pay_later no tiene ``journal_id``, asi
        que ``_get_cross_transitory_account`` caeria en el fallback de la POS
        receivable y lo daria por elegible sin este chequeo explicito.
        """
        pay_later_method = self.env["pos.payment.method"].create(
            {
                "name": "C Pay Later",
                "is_cash_count": False,
                "split_transactions": False,
                "company_id": self.company.id,
                "journal_id": False,
                "is_foreign_currency": True,
                "cross_account_journal": self.cross_account_journal.id,
                "cross_journal": self.real_bank_journal.id,
            }
        )
        self.assertEqual(pay_later_method.type, "pay_later")
        session = self._new_session().with_company(self.company)

        self.assertFalse(session._is_cross_move_eligible(pay_later_method))
        self.assertTrue(
            session._get_cross_transitory_account(pay_later_method),
            "el fallback si resuelve una cuenta: lo que excluye al metodo es el tipo",
        )

    # ------------------------------------------------------------------
    # Regresiones ya cubiertas antes de este refactor
    # ------------------------------------------------------------------
    def test_cross_move_name_takes_journal_sequence_on_post(self):
        """El asiento toma la secuencia de `cross_account_journal` al postearse.

        Antes del fix, `name` se fijaba con el literal "PoS Payment Method
        Adjustment" en el ``create()`` del ``account.move`` -- eso bloquea
        para siempre la asignacion nativa de secuencia
        (``_compute_name``/``_set_next_sequence`` solo corren cuando
        ``name`` esta vacio o es '/'). El texto descriptivo ahora va en
        ``ref``, dejando ``name`` libre para que Odoo lo asigne al postear.
        """
        self._configure_cross(self.split_bank_method)
        session = self._new_session().with_company(self.company)
        self._create_paid_order(
            session,
            method=self.split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=36.5,
            name="OL/CROSS/SEQUENCE",
        )

        session._validate_cross_move()

        move = self._cross_moves()
        self.assertEqual(len(move), 1)
        self.assertIn(
            move.name,
            (False, "/"),
            "en draft, name debe quedar vacio/'/' -- Odoo aun no asigno secuencia",
        )
        self.assertEqual(
            move.ref,
            "PoS Payment Method Adjustment",
            "el texto descriptivo vive en ref, no en name",
        )

        move.action_post()

        self.assertTrue(
            move.name and move.name != "/",
            "al postear, Odoo debe asignar la secuencia del diario cross_account_journal",
        )
        self.assertNotEqual(
            move.name,
            "PoS Payment Method Adjustment",
            "name NO debe quedar congelado con el literal viejo",
        )
        self.assertEqual(move.ref, "PoS Payment Method Adjustment", "ref se preserva tras postear")

    def test_amount_currency_uses_configured_foreign_currency_not_hardcoded_id(self):
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
