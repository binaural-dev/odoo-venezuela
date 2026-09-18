from collections import deque

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import drop_index, index_exists


@tagged("post_install", "-at_install", "l10n_ve_accountant", "unique_name_index")
class TestAccountMoveUniqueNameIndex(TransactionCase):
    """Cubre el ticket #14986: ante nombres de account.move duplicados,
    _auto_init no debe renombrar registros ni crashear -- solo debe omitir
    la creación del índice único y loguear un warning."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.partner_a = self.env["res.partner"].create({"name": "Proveedor A"})
        self.journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create({
            "name": "Compras Test 14986", "code": "T14986",
            "type": "purchase", "company_id": self.company.id,
        })
        drop_index(self.env.cr, "account_move_unique_name_ve", "account_move")
        drop_index(self.env.cr, "account_move_unique_name", "account_move")

    def _create_move(self, name, partner):
        """Crea un account.move y fuerza name/state directo en BD, simulando
        datos ya migrados/duplicados (el escenario real del bug)."""
        move = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": partner.id if partner else False,
            "journal_id": self.journal.id,
            "date": fields.Date.today(),
        })
        self.env.cr.execute(
            "UPDATE account_move SET state = 'posted', name = %s WHERE id = %s",
            (name, move.id),
        )
        move.invalidate_recordset()
        return move

    def _run_auto_init(self):
        """Reproduce el contexto transitorio que Registry.init_models() arma
        alrededor de model._auto_init() (post_init_queue, etc.) -- necesario
        porque estos atributos no existen fuera del ciclo de carga de módulos."""
        registry = self.env.registry
        registry._post_init_queue = deque()
        registry._foreign_keys = {}
        registry._is_install = False
        try:
            self.env["account.move"]._auto_init()
            while registry._post_init_queue:
                registry._post_init_queue.popleft()()
        finally:
            del registry._post_init_queue
            del registry._foreign_keys
            del registry._is_install

    def test_duplicate_names_are_not_renamed_but_real_duplicates_still_block_install(self):
        """Duplicados reales (mismo proveedor+diario+número): nuestro código
        no renombra nada y loguea el warning, pero la instalación igual se
        detiene -- Odoo core tampoco puede crear su propio índice sobre datos
        genuinamente duplicados. Es el comportamiento deseado: un problema de
        datos real debe frenar la migración para revisión manual, no
        ocultarse silenciosamente."""
        move_1 = self._create_move("FAC-DUP-001", self.partner_a)
        move_2 = self._create_move("FAC-DUP-001", self.partner_a)

        with self.assertLogs(
            "odoo.addons.l10n_ve_accountant.models.account_move", level="WARNING"
        ) as log_ctx:
            with self.assertRaises(IntegrityError):
                with self.env.cr.savepoint():
                    self._run_auto_init()

        self.assertTrue(
            any("account_move_unique_name_ve" in msg for msg in log_ctx.output),
            "Se esperaba un warning indicando que el índice no se reemplazó por duplicados",
        )
        move_1.invalidate_recordset()
        move_2.invalidate_recordset()
        self.assertEqual(
            move_1.name, "FAC-DUP-001",
            "El nombre no debe modificarse -- no debe agregarse ningún sufijo",
        )
        self.assertEqual(
            move_2.name, "FAC-DUP-001",
            "El nombre no debe modificarse -- no debe agregarse ningún sufijo",
        )
        self.assertFalse(
            index_exists(self.env.cr, "account_move_unique_name_ve"),
            "El índice único no debe crearse mientras existan duplicados",
        )

    def test_no_duplicates_creates_index(self):
        self._create_move("FAC-OK-001", self.partner_a)
        self._create_move("FAC-OK-002", self.partner_a)

        self._run_auto_init()

        self.assertTrue(
            index_exists(self.env.cr, "account_move_unique_name_ve"),
            "El índice único debe crearse cuando no hay duplicados",
        )
        self.assertTrue(
            index_exists(self.env.cr, "account_move_unique_name"),
            "El índice de core también debe recrearse con la definición ampliada",
        )

    def test_null_partner_id_is_not_a_false_positive(self):
        self._create_move("FAC-NULL-001", None)
        self._create_move("FAC-NULL-001", None)

        self._run_auto_init()

        self.assertTrue(
            index_exists(self.env.cr, "account_move_unique_name_ve"),
            "Registros con partner_id NULL no deben considerarse duplicados entre sí "
            "(replica el comportamiento real del índice único de postgres)",
        )
