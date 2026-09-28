from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteMultiCompanyJournalSearch(TransactionCase):
    """`_check_l10n_ve_exchange_debit_journal_sequences` busca el diario de
    ND de la compañía con `self.env['account.journal'].search(...)`, sin
    `.sudo()`. La regla `journal_comp_rule` (core `account`) filtra
    `account.journal` por `company_id parent_of company_ids`, donde
    `company_ids` en el eval context de `ir.rule` es
    `self.env.companies.ids` -- las compañías ACTIVAS en el selector del
    usuario (`allowed_company_ids` del contexto), no todas las que el
    usuario tiene asignadas (`res.users.company_ids`).

    Reproducido con un usuario real (`with_user`, no sudo) que tiene acceso
    a dos compañías pero solo una activa en su selector: el `search()`
    de un diario de la OTRA compañía (a la que sí tiene acceso, solo no
    está "activa" en ese momento) da vacío, aunque el diario exista. Esto
    confirma el bug que motivó pedir `.sudo()` en el commit original --
    nunca se había llegado a implementar pese a que el mensaje de commit y
    `openspec/changes/l10n-ve-exchange-difference-mixed-flow/tasks.md` lo
    marcaban como resuelto."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.ref("base.main_company")
        cls.company_b = cls.env["res.company"].create({"name": "Compañía B (ND)"})

        cls.debit_sequence = cls.env["ir.sequence"].create({
            "name": "ND Diferencial B",
            "code": "l10n_ve_exchange.debit_note.b",
            "company_id": cls.company_b.id,
        })
        cls.refund_sequence = cls.env["ir.sequence"].create({
            "name": "NC Diferencial B",
            "code": "l10n_ve_exchange.credit_note.b",
            "company_id": cls.company_b.id,
        })
        cls.sale_journal_b = cls.env["account.journal"].create({
            "name": "Ventas ND B",
            "type": "sale",
            "code": "VNDB",
            "company_id": cls.company_b.id,
            "is_debit": True,
            "l10n_ve_exchange_debit_note_sequence_id": cls.debit_sequence.id,
            "refund_sequence_id": cls.refund_sequence.id,
        })

        cls.exchange_gain_account_b = cls.env["account.account"].create({
            "name": "Exchange Gain B",
            "code": "770001B",
            "account_type": "income_other",
            "company_ids": [Command.set([cls.company_b.id])],
        })
        cls.exchange_loss_account_b = cls.env["account.account"].create({
            "name": "Exchange Loss B",
            "code": "670001B",
            "account_type": "expense",
            "company_ids": [Command.set([cls.company_b.id])],
        })
        cls.tax_group_b = cls.env["account.tax.group"].create({
            "name": "Tax Group B",
            "country_id": cls.company_b.country_id.id,
        })
        cls.exempt_tax_b = cls.env["account.tax"].create({
            "name": "Exempt Sale Tax B",
            "amount": 0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company_b.id,
            "tax_group_id": cls.tax_group_b.id,
        })
        cls.company_b.write({
            "income_currency_exchange_account_id": cls.exchange_gain_account_b.id,
            "expense_currency_exchange_account_id": cls.exchange_loss_account_b.id,
            "exent_aliquot_sale": cls.exempt_tax_b.id,
        })
        cls.note_product_b = cls.env["product.product"].create({
            "name": "Diferencial Cambiario ND/NC B",
            "type": "service",
        })
        cls.note_product_b.with_company(cls.company_b).write({
            "taxes_id": [Command.set([cls.exempt_tax_b.id])],
            "property_account_income_id": cls.exchange_gain_account_b.id,
            "property_account_expense_id": cls.exchange_loss_account_b.id,
        })
        cls.note_pricelist_b = cls.env["product.pricelist"].create({
            "name": "Lista ND/NC B",
            "currency_id": cls.company_b.currency_id.id,
        })
        cls.company_b.write({
            "l10n_ve_exchange_note_product_id": cls.note_product_b.id,
            "l10n_ve_exchange_note_pricelist_id": cls.note_pricelist_b.id,
        })

        cls.multi_company_user = cls.env["res.users"].create({
            "name": "Usuario Multi-Compañía",
            "login": "multi_company_exchange_user",
            "email": "multi_company_exchange_user@example.com",
            "group_ids": [Command.set([
                cls.env.ref("base.group_system").id,
                cls.env.ref("account.group_account_manager").id,
            ])],
            "company_id": cls.company_a.id,
            "company_ids": [Command.set([cls.company_a.id, cls.company_b.id])],
        })

    def test_journal_search_hidden_with_restricted_allowed_company_ids(self):
        """El mismo `search()` que usa
        `_check_l10n_ve_exchange_debit_journal_sequences`, ejecutado como
        el usuario multi-compañía con SOLO la compañía A activa en
        `allowed_company_ids`, NO encuentra el diario de la compañía B
        aunque exista y esté correctamente configurado -- confirma que
        `.sudo()` hace falta en el método real."""
        restricted_journal_model = self.env["account.journal"].with_user(
            self.multi_company_user
        ).with_context(allowed_company_ids=[self.company_a.id])
        found_without_sudo = restricted_journal_model.search([
            ("company_id", "=", self.company_b.id),
            ("is_debit", "=", True),
            ("type", "=", "sale"),
        ], order="id", limit=1)
        self.assertFalse(
            found_without_sudo,
            "Si esto empieza a encontrar el diario, el bug de "
            "journal_comp_rule ya no aplica -- revisar si el .sudo() "
            "de _check_l10n_ve_exchange_debit_journal_sequences sigue "
            "siendo necesario.",
        )

        found_with_sudo = restricted_journal_model.sudo().search([
            ("company_id", "=", self.company_b.id),
            ("is_debit", "=", True),
            ("type", "=", "sale"),
        ], order="id", limit=1)
        self.assertEqual(
            found_with_sudo, self.sale_journal_b,
            "Con .sudo(), el mismo search() sí debe encontrar el diario "
            "de la compañía B pese al allowed_company_ids restringido.",
        )

    def test_constraint_passes_thanks_to_sudo_with_restricted_allowed_company_ids(self):
        """Ejercita el método REAL (`_check_l10n_ve_exchange_debit_journal_sequences`,
        no una réplica de su query) a través del flujo público que lo
        dispara -- activar el toggle en la compañía -- con el mismo
        usuario/contexto restringido del test anterior. Si el `.sudo()`
        del método se quitara, este `write()` levantaría la
        `ValidationError` de "configure a sale journal..." pese a que el
        diario de ND de la compañía B sí existe y está bien configurado."""
        company_b_restricted = self.company_b.with_user(
            self.multi_company_user
        ).with_context(allowed_company_ids=[self.company_a.id])
        company_b_restricted.write({"l10n_ve_exchange_use_nd_nc": True})
        self.assertTrue(self.company_b.l10n_ve_exchange_use_nd_nc)
