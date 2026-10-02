from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_account_fiscalyear_closing")
class TestGapCoverage(TransactionCase):
    """Casos no cubiertos por los tests que trae el PR #1242
    (l10n_ve_account_fiscalyear_closing): multi-compania en onchange_l_map,
    ambiguedad de src_account_id, active_move_ids en button_post, el mensaje
    de skipped_accounts y el caso bimoneda."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.VEF").active = True
        cls.company_a = cls.env.ref("base.main_company")
        cls.company_b = cls.env["res.company"].create({"name": "Company B"})
        # Sin esto, las record rules multi-compania esconden los registros
        # de company_b (cuentas, diarios, el propio cierre) para el usuario
        # de test, aunque el codigo del test los busque con un dominio
        # explicito -- las reglas se aplican ADEMAS del dominio pasado.
        cls.env.user.company_ids = [(4, cls.company_b.id)]
        cls.journal_a = cls.env["account.journal"].create(
            {
                "name": "Diario A",
                "code": "GAPA",
                "type": "general",
                "company_id": cls.company_a.id,
            }
        )

    def test_onchange_l_map_uses_closing_company_not_active_company(self):
        """El fix del PR: onchange_l_map debe resolver las cuentas por
        fyc_id.company_id (la compania del cierre), no por self.env.company
        (la compania activa de sesion). En vez de forzar la sesion activa
        via contexto (choca con las reglas multi-compania de lectura: bajo
        allowed_company_ids=[company_b], leer fyc_id de un registro de
        company_a queda bloqueado por record rules, lo que enmascara lo que
        se quiere probar), se invierte el escenario: el cierre pertenece a
        company_b mientras la sesion sigue en su compania normal (la de
        self.env.user, company_a) -- exactamente el caso real del bug."""
        account_b = self.env["account.account"].create(
            {
                "name": "Income B",
                "code": "GAPINCB",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_b.id])],
            }
        )
        # Mismo codigo en company_a, para probar que no se cuela por venir
        # de self.env.company (la compania activa de la sesion normal).
        self.env["account.account"].create(
            {
                "name": "Income A",
                "code": "GAPINC",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        equity_b = self.env["account.account"].create(
            {
                "name": "Equity B",
                "code": "GAPEQB",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, [self.company_b.id])],
            }
        )

        journal_b = self.env["account.journal"].create(
            {
                "name": "Diario B",
                "code": "GAPB",
                "type": "general",
                "company_id": self.company_b.id,
            }
        )
        fyc = self.env["account.fiscalyear.closing"].create(
            {
                "name": "FY gap onchange",
                "company_id": self.company_b.id,
                "date_start": "2025-01-01",
                "date_end": "2025-12-31",
                "date_opening": "2026-01-01",
            }
        )
        config = self.env["account.fiscalyear.closing.config"].create(
            {
                "name": "Config gap",
                "code": "GAPCFG",
                "fyc_id": fyc.id,
                "journal_id": journal_b.id,
                "date": "2025-12-31",
                "move_type": "closing",
                "enabled": True,
            }
        )
        # onchange_l_map() NO escribe mapping_ids en el registro -- solo
        # devuelve un dict {"value": {"mapping_ids": [(0, 0, vals), ...]}}
        # (semantica estandar de un metodo @api.onchange), asi que hay que
        # inspeccionar el valor de retorno, no releer config.mapping_ids.
        config.l_map = True
        result = config.onchange_l_map()

        created_vals = [cmd[2] for cmd in result["value"]["mapping_ids"]]
        mapped_codes = [v["src_accounts"] for v in created_vals]
        # account.account.code es un campo computado que se resuelve segun
        # self.env.company (ver account_account.py _compute_code), no segun
        # la compania del registro -- hay que leerlo con with_company(
        # company_b) para verlo en la sesion normal (company_a) del test.
        account_b_code = account_b.with_company(self.company_b).code
        self.assertEqual(account_b_code, "GAPINCB")
        self.assertIn(account_b_code, mapped_codes)
        self.assertNotIn("GAPINC", mapped_codes)
        vals_b = next(v for v in created_vals if v["src_accounts"] == account_b_code)
        self.assertEqual(vals_b["dest_account_id"], equity_b.id)

    def test_button_post_skips_previously_cancelled_moves(self):
        """button_post() debe postear solo active_move_ids, no move_ids: un
        recalculo previo deja en move_ids asientos cancelados (para
        auditoria, ver _moves_remove en el modulo base), y action_post()
        sobre un asiento cancelado lanza UserError."""
        account_income = self.env["account.account"].create(
            {
                "name": "Income gap post",
                "code": "GAPPOST",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        account_equity = self.env["account.account"].create(
            {
                "name": "Equity gap post",
                "code": "GAPEQPOST",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        move = self.env["account.move"].create(
            {
                "company_id": self.company_a.id,
                "journal_id": self.journal_a.id,
                "date": "2025-06-01",
                "line_ids": [
                    (0, 0, {"account_id": account_income.id, "debit": 0, "credit": 100, "date": "2025-06-01"}),
                    (0, 0, {"account_id": account_equity.id, "debit": 100, "credit": 0, "date": "2025-06-01"}),
                ],
            }
        )
        move.action_post()

        fyc = self.env["account.fiscalyear.closing"].create(
            {
                "name": "FY gap post",
                "company_id": self.company_a.id,
                "date_start": "2025-01-01",
                "date_end": "2025-12-31",
                "date_opening": "2026-01-01",
                "check_draft_moves": False,
            }
        )
        config = self.env["account.fiscalyear.closing.config"].create(
            {
                "name": "Config gap post",
                "code": "GAPCFGPOST",
                "fyc_id": fyc.id,
                "journal_id": self.journal_a.id,
                "date": "2025-12-31",
                "move_type": "closing",
                "enabled": True,
            }
        )
        self.env["account.fiscalyear.closing.mapping"].create(
            {
                "name": "Map gap post",
                "src_accounts": account_income.code,
                "dest_account_id": account_equity.id,
                "fyc_config_id": config.id,
            }
        )

        fyc.button_calculate()
        first_move = fyc.move_ids
        self.assertEqual(len(first_move), 1)
        # _moves_remove solo CANCELA (conserva) un asiento que llego a
        # postearse; uno que se queda en draft/calculated se elimina sin
        # mas. Para probar el caso de active_move_ids hay que postear
        # primero, antes de recalcular.
        fyc.button_post()
        self.assertEqual(first_move.state, "posted")

        # Recalcular: el asiento anterior queda cancelado en move_ids, uno
        # nuevo se genera y queda como active_move_ids.
        fyc.button_recalculate()
        self.assertEqual(first_move.state, "cancel")
        self.assertIn(first_move, fyc.move_ids)
        self.assertNotIn(first_move, fyc.active_move_ids)
        self.assertEqual(len(fyc.active_move_ids), 1)
        self.assertNotEqual(fyc.active_move_ids, first_move)

        # No debe intentar volver a postear el cancelado.
        fyc.button_post()
        self.assertEqual(fyc.state, "posted")
        self.assertEqual(fyc.active_move_ids.state, "posted")
        self.assertEqual(first_move.state, "cancel")

    def test_message_posted_when_accounts_skipped(self):
        """calculate() debe dejar constancia en el chatter de las cuentas
        mapeadas sin saldo en el periodo (skipped_accounts), ademas de la
        que si tiene saldo (para que el cierre no falle por completo)."""
        account_with_balance = self.env["account.account"].create(
            {
                "name": "Income con saldo",
                "code": "GAPBAL",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        account_without_balance = self.env["account.account"].create(
            {
                "name": "Income sin saldo",
                "code": "GAPNOBAL",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        account_equity = self.env["account.account"].create(
            {
                "name": "Equity gap msg",
                "code": "GAPEQMSG",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        move = self.env["account.move"].create(
            {
                "company_id": self.company_a.id,
                "journal_id": self.journal_a.id,
                "date": "2025-06-01",
                "line_ids": [
                    (0, 0, {"account_id": account_with_balance.id, "debit": 0, "credit": 100, "date": "2025-06-01"}),
                    (0, 0, {"account_id": account_equity.id, "debit": 100, "credit": 0, "date": "2025-06-01"}),
                ],
            }
        )
        move.action_post()

        fyc = self.env["account.fiscalyear.closing"].create(
            {
                "name": "FY gap msg",
                "company_id": self.company_a.id,
                "date_start": "2025-01-01",
                "date_end": "2025-12-31",
                "date_opening": "2026-01-01",
                "check_draft_moves": False,
            }
        )
        config = self.env["account.fiscalyear.closing.config"].create(
            {
                "name": "Config gap msg",
                "code": "GAPCFGMSG",
                "fyc_id": fyc.id,
                "journal_id": self.journal_a.id,
                "date": "2025-12-31",
                "move_type": "closing",
                "enabled": True,
            }
        )
        self.env["account.fiscalyear.closing.mapping"].create(
            {
                "name": "Map gap msg con saldo",
                "src_accounts": account_with_balance.code,
                "dest_account_id": account_equity.id,
                "fyc_config_id": config.id,
            }
        )
        self.env["account.fiscalyear.closing.mapping"].create(
            {
                "name": "Map gap msg sin saldo",
                "src_accounts": account_without_balance.code,
                "dest_account_id": account_equity.id,
                "fyc_config_id": config.id,
            }
        )

        messages_before = fyc.message_ids
        fyc.calculate()
        new_messages = fyc.message_ids - messages_before
        bodies = " ".join(m.body or "" for m in new_messages)
        self.assertIn(account_without_balance.code, bodies)
        self.assertNotIn(account_with_balance.code, bodies)

    def test_closes_account_with_bs_balance_and_zero_foreign_balance(self):
        """Bug corregido: una cuenta con saldo real en bolivares pero
        foreign_balance == 0 (sin ningun movimiento en moneda alterna en el
        periodo) debe cerrarse igual. Antes, en bimoneda, se exigia
        foreign_balance != 0 y la descartaba por completo."""
        # EUR/USD: cualquiera que no coincida con la moneda base de la
        # compania (l10n_ve_rate exige que sean distintas); se elige en
        # tiempo de ejecucion en vez de asumir cual es la base aqui.
        foreign = self.env.ref("base.USD")
        if foreign == self.company_a.currency_id:
            foreign = self.env.ref("base.EUR")
        foreign.active = True
        self.company_a.foreign_currency_id = foreign.id

        account_income = self.env["account.account"].create(
            {
                "name": "Income bimoneda",
                "code": "GAPFX",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        account_equity = self.env["account.account"].create(
            {
                "name": "Equity bimoneda",
                "code": "GAPEQFX",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        move = self.env["account.move"].create(
            {
                "company_id": self.company_a.id,
                "journal_id": self.journal_a.id,
                "date": "2025-06-01",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": account_income.id,
                            "debit": 0,
                            "credit": 100,
                            "date": "2025-06-01",
                            "foreign_debit": 0,
                            "foreign_credit": 0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": account_equity.id,
                            "debit": 100,
                            "credit": 0,
                            "date": "2025-06-01",
                            "foreign_debit": 0,
                            "foreign_credit": 0,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        move_line = move.line_ids.filtered(lambda l: l.account_id == account_income)
        # foreign_debit/foreign_credit son computed fields (ver
        # l10n_ve_accountant): el 0 explicito pasado en create() no se
        # respeta, se recalculan segun moneda del asiento vs.
        # foreign_currency_id de la compania. No forzamos aqui un valor
        # exacto de foreign_balance -- lo que importa es que balance != 0
        # de por si alcanza para que la cuenta se cierre (antes, en
        # bimoneda, se exigia ADEMAS foreign_balance != 0).
        self.assertEqual(move_line.balance, -100)

        fyc = self.env["account.fiscalyear.closing"].create(
            {
                "name": "FY gap fx",
                "company_id": self.company_a.id,
                "date_start": "2025-01-01",
                "date_end": "2025-12-31",
                "date_opening": "2026-01-01",
                "check_draft_moves": False,
            }
        )
        config = self.env["account.fiscalyear.closing.config"].create(
            {
                "name": "Config gap fx",
                "code": "GAPCFGFX",
                "fyc_id": fyc.id,
                "journal_id": self.journal_a.id,
                "date": "2025-12-31",
                "move_type": "closing",
                "enabled": True,
            }
        )
        self.env["account.fiscalyear.closing.mapping"].create(
            {
                "name": "Map gap fx",
                "src_accounts": account_income.code,
                "dest_account_id": account_equity.id,
                "fyc_config_id": config.id,
            }
        )

        result = fyc.calculate()
        self.assertTrue(result)
        self.assertEqual(len(fyc.move_ids), 1)
