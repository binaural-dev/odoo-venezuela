"""Closing note of the cashier.

Odoo 19 sent the note typed in the closing popup to the server
(``update_closing_control_state_session``) and stored it in
``pos.session.closing_notes``. Odoo 20 keeps it in the popup state and never
sends it, so ``l10n_ve_pos`` restores it with ``update_closing_notes``. It
also posted in the chatter of the session the closing difference, the expected
and the counted cash with the note; Odoo 20 posts only the opening one, so
``l10n_ve_pos`` posts it again at closing.
"""

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import html2plaintext

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

    def _closing_messages(self, session):
        return session.message_ids.filtered(lambda m: "Closing difference" in (m.body or ""))

    def test_closing_posts_the_cash_details_once(self):
        session = self._open_session()
        self._close(session, 5.0)
        messages = self._closing_messages(session)
        self.assertEqual(len(messages), 1)
        body = html2plaintext(messages.body)
        money = session.currency_id.format
        self.assertIn("Closing difference: %s" % money(5.0), body)
        self.assertIn("Closing expected: %s" % money(0.0), body)
        self.assertIn("Closing counted: %s" % money(5.0), body)

    def test_closing_message_carries_the_note(self):
        session = self._open_session()
        session.update_closing_notes("cash short by two bills")
        self._close(session, 0.0)
        body = html2plaintext(self._closing_messages(session).body)
        self.assertIn("Opening control message: cash short by two bills", body)

    def test_closing_message_without_note_has_no_note_line(self):
        session = self._open_session()
        self._close(session, 0.0)
        self.assertNotIn("control message", html2plaintext(self._closing_messages(session).body))

    def test_opening_posts_no_closing_message(self):
        session = self._open_session()
        self.assertFalse(self._closing_messages(session))

    def test_message_shows_the_count_of_the_register_apart_from_the_offset(self):
        session = self._open_session()
        with patch.object(type(session), "_get_closing_cash_offset", return_value=10.0):
            session.update_closing_notes("")
            session.close_session_from_ui({self.cash_method.id: 5.0})
        body = html2plaintext(self._closing_messages(session).body)
        money = session.currency_id.format
        self.assertIn("Closing difference: %s" % money(5.0), body)
        self.assertIn("Closing expected: %s" % money(-10.0), body)
        self.assertIn("Closing counted: %s" % money(-5.0), body)
