from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestAccountMoveButtonDraftMultiRecord(TestPoSCommon):
    """Regresión ticket #15340: `button_draft` fallaba con
    `ValueError: Expected singleton` al resetear a borrador varios
    `account.move` a la vez (p.e. al cancelar una retención de IVA con
    varios pagos asociados) mientras había una sesión de PoS abierta en la
    compañía, porque evaluaba `self.id` sobre un recordset multi-registro
    en lugar de iterar `self`.
    """

    @classmethod
    def setup_company_data(cls, company_name, chart_template=None, **kwargs):
        # Corre antes de que AccountTestInvoicingCommon cree product_b (dos
        # impuestos de la misma compañía), que dispara el constraint
        # _check_taxes_id de l10n_ve_stock. Se desactiva solo durante esta
        # clase de test (mismo patrón que TestPosSessionForeignClose).
        cls._disable_ve_single_tax_constraint()
        return super().setup_company_data(
            company_name, chart_template=chart_template, **kwargs
        )

    @classmethod
    def _disable_ve_single_tax_constraint(cls):
        if getattr(cls, "_ve_tax_constraint_patched", False):
            return
        cls._ve_tax_constraint_patched = True
        template_cls = cls.env.registry["product.template"]
        original = cls.env["product.template"]._constraint_methods
        template_cls._constraint_methods = [
            method
            for method in original
            if getattr(method, "__name__", "") != "_check_taxes_id"
        ]
        cls.addClassCleanup(setattr, template_cls, "_constraint_methods", original)

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref or "generic_coa")
        cls.config = cls.basic_config
        cls.retention_partner = cls.env["res.partner"].create(
            {"name": "Cliente Test Retencion #15340"}
        )

        # Sin moneda alterna configurada, `_compute_foreign_subtotal` de
        # l10n_ve_accountant revienta al hacer flush de las líneas creadas
        # en _create_posted_move (mismo setup que TestPoSCommon.setUpClass
        # usa para sus propios casos de moneda foránea).
        foreign_currency = cls.env.ref("base.VEF")
        foreign_currency.active = True
        cls.company.currency_foreign_id = foreign_currency
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": foreign_currency.id,
                "company_id": cls.company.id,
                "company_rate": 36.0,
            }
        )

    def _create_posted_move(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.company_data["default_journal_misc"].id,
                "partner_id": self.retention_partner.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 100.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 100.0,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def test_button_draft_multi_record_with_open_pos_session(self):
        """Cancelar/resetear varios asientos a la vez (como hace
        `account.payment.action_cancel` sobre `payment_ids.move_id` al
        anular una retención con varios pagos) no debe romper por
        singleton mientras haya una sesión de PoS abierta.

        La sesión se crea a bajo nivel (sin `open_new_session`/`open_ui`)
        porque lo único que el código bajo prueba necesita es que exista un
        `pos.session` en estado `opened` para la compañía; no hace falta
        pasar por toda la validación de apertura real (moneda foránea,
        efectivo inicial, etc.), que es ortogonal a este bug.
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.uid,
            }
        )
        session.write({"state": "opened"})

        moves = self._create_posted_move() + self._create_posted_move()
        self.assertEqual(len(moves), 2)

        moves.button_draft()

        self.assertTrue(all(move.state == "draft" for move in moves))

    def test_button_draft_multi_record_raises_when_one_move_is_linked_to_session(self):
        """Si alguno de los asientos del lote SÍ está vinculado a la
        sesión de PoS abierta (vía `pos.session.move_id`, que forma parte
        de `_get_related_account_moves`), debe seguir bloqueando el draft
        con `UserError`, aunque el lote tenga varios registros."""
        linked_move = self._create_posted_move()
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.uid,
            }
        )
        session.write({"state": "opened", "move_id": linked_move.id})

        other_move = self._create_posted_move()
        moves = linked_move + other_move

        with self.assertRaises(UserError):
            moves.button_draft()

    def test_button_draft_multi_record_allowed_when_pos_move_to_draft(self):
        """Con `pos_move_to_draft` activo en la compañía, debe poder
        resetear a borrador aunque el asiento esté vinculado a la sesión
        abierta."""
        linked_move = self._create_posted_move()
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.uid,
            }
        )
        session.write({"state": "opened", "move_id": linked_move.id})
        self.company.pos_move_to_draft = True

        linked_move.button_draft()

        self.assertEqual(linked_move.state, "draft")
