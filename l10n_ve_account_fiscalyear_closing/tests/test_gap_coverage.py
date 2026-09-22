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
        (la compania activa de sesion). Se simula sesion activa en company_b
        mientras el cierre pertenece a company_a: solo deben aparecer
        cuentas de company_a en el mapping generado."""
        account_a = self.env["account.account"].create(
            {
                "name": "Income A",
                "code": "GAPINC",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )
        # Misma codificacion en company_b para probar que no se cuela.
        self.env["account.account"].create(
            {
                "name": "Income B",
                "code": "GAPINCB",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company_b.id])],
            }
        )
        equity_a = self.env["account.account"].create(
            {
                "name": "Equity A",
                "code": "GAPEQA",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, [self.company_a.id])],
            }
        )

        fyc = self.env["account.fiscalyear.closing"].create(
            {
                "name": "FY gap onchange",
                "company_id": self.company_a.id,
                "date_start": "2025-01-01",
                "date_end": "2025-12-31",
                "date_opening": "2026-01-01",
            }
        )
        config = self.env["account.fiscalyear.closing.config"].with_context(
            allowed_company_ids=[self.company_b.id]
        ).create(
            {
                "name": "Config gap",
                "code": "GAPCFG",
                "fyc_id": fyc.id,
                "journal_id": self.journal_a.id,
                "date": "2025-12-31",
                "move_type": "closing",
                "enabled": True,
            }
        )
        # Sesion activa en company_b; el cierre sigue siendo de company_a.
        config = config.with_context(allowed_company_ids=[self.company_b.id])
        config.l_map = True
        config.with_user(self.env.user).with_context(
            company_id=self.company_b.id
        ).onchange_l_map()

        mapped_codes = config.mapping_ids.mapped("src_accounts")
        self.assertIn(account_a.code, mapped_codes)
        self.assertNotIn("GAPINCB", mapped_codes)
        self.assertEqual(
            config.mapping_ids.filtered(lambda m: m.src_accounts == account_a.code)
            .dest_account_id,
            equity_a,
        )

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
        self.company_a.foreign_currency_id = self.env.ref("base.USD").id

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
        self.assertEqual(move_line.foreign_balance, 0)
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
