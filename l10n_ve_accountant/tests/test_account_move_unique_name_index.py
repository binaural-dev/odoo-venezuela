from collections import deque

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import index_exists
from odoo.tools.sql import drop_index, index_definition


@tagged("post_install", "-at_install", "l10n_ve_accountant", "unique_name_index")
class TestAccountMoveUniqueNameIndex(TransactionCase):
    """Ticket #14986: with duplicated account.move numbers, _auto_init must not rename records.
    It stops the install with its own readable UserError and does not create the unique index."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.partner_a = self.env["res.partner"].create({"name": "Proveedor A"})
        self.partner_b = self.env["res.partner"].create({"name": "Proveedor B"})
        self.journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create(
            {
                "name": "Compras Test 14986",
                "code": "T14986",
                "type": "purchase",
                "company_id": self.company.id,
            }
        )
        drop_index(self.env.cr, "account_move_unique_name_ve", "account_move")
        drop_index(self.env.cr, "account_move_unique_name", "account_move")

    def _create_move(self, name, partner):
        """Create a move and force name/state in the database, as migrated data would arrive."""
        move = (
            self.env["account.move"]
            .with_context(check_move_validity=False)
            .create(
                {
                    "move_type": "in_invoice",
                    "partner_id": partner.id if partner else False,
                    "journal_id": self.journal.id,
                    "date": fields.Date.today(),
                }
            )
        )
        self.env.cr.execute(
            "UPDATE account_move SET state = 'posted', name = %s WHERE id = %s",
            (name, move.id),
        )
        move.invalidate_recordset()
        return move

    def _run_auto_init(self):
        """Rebuild the transient context Registry.init_models() sets around model._auto_init()."""
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

    def test_duplicate_names_are_not_renamed_but_block_install(self):
        """Real duplicates (same partner, journal and number): nothing is renamed, and the
        install stops with an error naming the partner, journal and number."""
        move_1 = self._create_move("FAC-DUP-001", self.partner_a)
        move_2 = self._create_move("FAC-DUP-001", self.partner_a)

        with self.assertRaises(UserError) as error_ctx:
            self._run_auto_init()

        message = str(error_ctx.exception)
        self.assertIn("FAC-DUP-001", message)
        self.assertIn(self.partner_a.name, message)
        self.assertIn(self.journal.name, message)
        self.assertEqual(move_1.name, "FAC-DUP-001", "No suffix must be added to the number")
        self.assertEqual(move_2.name, "FAC-DUP-001", "No suffix must be added to the number")
        self.assertFalse(
            index_exists(self.env.cr, "account_move_unique_name_ve"),
            "The unique index must not be created while duplicates exist",
        )

    def test_no_duplicates_creates_index(self):
        self._create_move("FAC-OK-001", self.partner_a)
        self._create_move("FAC-OK-002", self.partner_a)

        self._run_auto_init()

        self.assertTrue(index_exists(self.env.cr, "account_move_unique_name_ve"))
        self.assertTrue(index_exists(self.env.cr, "account_move_unique_name"))

    def test_core_keeps_the_wider_index(self):
        """In 19 core declares account_move_unique_name as a table object on (name, journal_id):
        after the whole _auto_init it must still be the index that includes the partner."""
        self._create_move("FAC-SHARED-001", self.partner_a)
        self._create_move("FAC-SHARED-001", self.partner_b)

        self._run_auto_init()

        definition, _comment = index_definition(self.env.cr, "account_move_unique_name")
        self.assertIn("partner_id", definition)
        self.assertIn("company_id", definition)

    def test_null_partner_id_is_not_a_false_positive(self):
        self._create_move("FAC-NULL-001", None)
        self._create_move("FAC-NULL-001", None)

        self._run_auto_init()

        self.assertTrue(
            index_exists(self.env.cr, "account_move_unique_name_ve"),
            "Moves without partner are not duplicates of each other (as in the postgres index)",
        )
