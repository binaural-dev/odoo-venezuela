from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant", "foreign_amount")
class TestForeignBalanceEntry(TransactionCase):
    """
    El monto alterno (foreign_debit/foreign_credit) de un asiento manual debe
    seguir el lado de la línea en moneda base. Si una línea pasa de crédito a
    débito (p. ej. la contrapartida que Odoo propone como crédito y el usuario
    convierte en débito), el lado que queda en cero no debe conservar el monto
    alterno anterior, o el asiento queda descuadrado en la moneda alterna.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "currency_id": cls.currency_vef.id,
                "currency_foreign_id": cls.currency_usd.id,
            }
        )
        cls.account_a = cls.env["account.account"].create(
            {"name": "Test Expense A", "code": "TFB001", "account_type": "expense"}
        )
        cls.account_b = cls.env["account.account"].create(
            {
                "name": "Test Liability B",
                "code": "TFB002",
                "account_type": "liability_current",
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].create(
            {
                "name": "Test Misc Ops",
                "type": "general",
                "code": "TFBMI",
                "company_id": cls.company.id,
            }
        )
        cls.foreign_rate = 50.0
        cls.foreign_inverse_rate = 0.02  # 1 / 50

    def _foreign_diff(self, move):
        return sum(move.line_ids.mapped("foreign_debit")) - sum(
            move.line_ids.mapped("foreign_credit")
        )

    def test_line_switching_side_clears_old_foreign_amount(self):
        move = self.env["account.move"].create(
            {
                "journal_id": self.journal.id,
                "manually_set_rate": True,
                "foreign_rate": self.foreign_rate,
                "foreign_inverse_rate": self.foreign_inverse_rate,
                "line_ids": [
                    Command.create(
                        {"name": "A", "account_id": self.account_a.id, "debit": 1000.0}
                    ),
                    Command.create(
                        {"name": "B", "account_id": self.account_b.id, "credit": 1000.0}
                    ),
                ],
            }
        )
        line_a = move.line_ids.filtered(lambda l: l.name == "A")
        line_b = move.line_ids.filtered(lambda l: l.name == "B")
        self.assertAlmostEqual(line_a.foreign_debit, 20.0)
        self.assertAlmostEqual(line_b.foreign_credit, 20.0)

        move.write(
            {
                "line_ids": [
                    Command.update(line_a.id, {"debit": 0.0, "credit": 1000.0}),
                    Command.update(line_b.id, {"debit": 1000.0, "credit": 0.0}),
                ]
            }
        )

        self.assertAlmostEqual(line_a.foreign_debit, 0.0)
        self.assertAlmostEqual(line_a.foreign_credit, 20.0)
        self.assertAlmostEqual(line_b.foreign_debit, 20.0)
        self.assertAlmostEqual(line_b.foreign_credit, 0.0)
        self.assertAlmostEqual(self._foreign_diff(move), 0.0)
