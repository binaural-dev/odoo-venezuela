"""Closing note of the cashier.

Odoo 19 sent the note typed in the closing popup to the server
(``update_closing_control_state_session``) and stored it in
``pos.session.closing_notes``. Odoo 20 keeps it in the popup state and never
sends it, so ``l10n_ve_pos`` restores it with ``update_closing_notes``.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionClosingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_closing_notes")
class TestPosClosingNotes(TestPosSessionClosingBase):
    def test_note_is_stored_and_survives_the_closing(self):
        session = self._open_session()
        self.assertTrue(session.update_closing_notes("cash short by two bills"))
        self.assertEqual(session.closing_notes, "cash short by two bills")
        self._close(session, 0.0)
        self.assertEqual(session.state, "closed")
        self.assertEqual(session.closing_notes, "cash short by two bills")

    def test_last_note_wins_and_empty_clears_it(self):
        session = self._open_session()
        session.update_closing_notes("first")
        session.update_closing_notes("second")
        self.assertEqual(session.closing_notes, "second")
        session.update_closing_notes("")
        self.assertFalse(session.closing_notes)

    def test_closed_session_keeps_its_note(self):
        session = self._open_session()
        session.update_closing_notes("final")
        self._close(session, 0.0)
        self.assertFalse(session.update_closing_notes("late"))
        self.assertEqual(session.closing_notes, "final")

    def test_user_without_pos_access_cannot_write_it(self):
        session = self._open_session()
        portal = self.env["res.users"].create(
            {
                "name": "Portal closing",
                "login": "portal_closing_notes",
                "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )
        with self.assertRaises(AccessError):
            session.with_user(portal).update_closing_notes("x")
