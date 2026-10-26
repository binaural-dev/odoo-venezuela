import logging
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)

REPORT_REF = "l10n_ve_payment_extension.retention_voucher_template"
TYPES = ("iva", "islr", "municipal")


@tagged("post_install", "-at_install", "retention_voucher_buttons")
class TestRetentionVoucherButtons(RetentionTestCommon):
    """Voucher download buttons on the document and on the retention (#15936)."""

    def _create_move(self):
        return self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )

    def _create_retention(self, type_retention, move=None, state="emitted", **extra):
        move = move or self._create_move()
        vals = {
            "type_retention": type_retention,
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [(0, 0, {
                "move_id": move.id,
                "invoice_amount": 200.0,
                "retention_amount": 10.0,
            })],
        }
        vals.update(extra)
        retention = self.env["account.retention"].create(vals)
        retention.write({"state": state})
        return retention

    def _download(self, move, retention_type):
        return move.with_context(
            retention_type=retention_type
        ).action_download_retention_voucher()

    def _assert_report_action(self, action, retentions):
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(action["report_name"], REPORT_REF)
        self.assertEqual(sorted(action["context"]["active_ids"]), sorted(retentions.ids))

    def test_01_document_button_returns_report_for_each_type(self):
        for retention_type in TYPES:
            retention = self._create_retention(retention_type)
            move = retention.retention_line_ids.move_id
            self._assert_report_action(self._download(move, retention_type), retention)
        _logger.info("========= test_01 passed =========")

    def test_02_document_button_without_emitted_retention_raises(self):
        move = self._create_move()
        for retention_type in TYPES:
            with self.assertRaises(UserError):
                self._download(move, retention_type)
        _logger.info("========= test_02 passed =========")

    def test_03_document_button_unknown_type_raises(self):
        retention = self._create_retention("iva")
        move = retention.retention_line_ids.move_id
        with self.assertRaises(UserError):
            self._download(move, "other")
        with self.assertRaises(UserError):
            move.action_download_retention_voucher()
        _logger.info("========= test_03 passed =========")

    def test_04_document_button_ignores_draft_and_cancelled(self):
        move = self._create_move()
        self._create_retention("islr", move=move, state="draft")
        self._create_retention("islr", move=move, state="cancel")
        with self.assertRaises(UserError):
            self._download(move, "islr")
        emitted = self._create_retention("islr", move=move)
        self._assert_report_action(self._download(move, "islr"), emitted)
        _logger.info("========= test_04 passed =========")

    def test_05_document_button_groups_retentions_of_the_same_type(self):
        move = self._create_move()
        first = self._create_retention("iva", move=move)
        second = self._create_retention("iva", move=move)
        self._assert_report_action(self._download(move, "iva"), first | second)
        _logger.info("========= test_05 passed =========")

    def test_06_document_button_does_not_mix_types(self):
        move = self._create_move()
        iva = self._create_retention("iva", move=move)
        self._create_retention("islr", move=move)
        self._assert_report_action(self._download(move, "iva"), iva)
        _logger.info("========= test_06 passed =========")

    def test_07_document_button_sets_municipal_delivery_date_once(self):
        retention = self._create_retention("municipal", date_emision=False)
        move = retention.retention_line_ids.move_id
        self._download(move, "municipal")
        self.assertEqual(retention.date_emision, fields.Date.today())
        previous = fields.Date.today() - timedelta(days=3)
        retention.date_emision = previous
        self._download(move, "municipal")
        self.assertEqual(retention.date_emision, previous)
        _logger.info("========= test_07 passed =========")

    def test_08_retention_button_returns_report_for_each_type(self):
        for retention_type in TYPES:
            retention = self._create_retention(retention_type)
            self._assert_report_action(
                retention.action_print_retention_voucher_pdf(), retention
            )
        _logger.info("========= test_08 passed =========")

    def test_09_retention_button_requires_emitted_state(self):
        for state in ("draft", "cancel"):
            for retention_type in TYPES:
                retention = self._create_retention(retention_type, state=state)
                with self.assertRaises(UserError):
                    retention.action_print_retention_voucher_pdf()
        _logger.info("========= test_09 passed =========")

    def test_10_retention_button_sets_municipal_delivery_date_once(self):
        retention = self._create_retention("municipal", date_emision=False)
        retention.action_print_retention_voucher_pdf()
        self.assertEqual(retention.date_emision, fields.Date.today())
        previous = fields.Date.today() - timedelta(days=3)
        retention.date_emision = previous
        retention.action_print_retention_voucher_pdf()
        self.assertEqual(retention.date_emision, previous)
        _logger.info("========= test_10 passed =========")

    def test_11_retention_button_does_not_touch_other_types_delivery_date(self):
        retention = self._create_retention("iva")
        retention.action_print_retention_voucher_pdf()
        self.assertFalse(retention.date_emision)
        _logger.info("========= test_11 passed =========")

    def _button_invisible(self, model, view_xmlid, method, string=None):
        view = self.env.ref(f"l10n_ve_payment_extension.{view_xmlid}")
        arch = self.env[model].get_view(view.id)["arch"]
        buttons = re.findall(r"<button\b[^>]*>", arch)
        found = [
            button for button in buttons
            if f'name="{method}"' in button and (string is None or string in button)
        ]
        self.assertEqual(len(found), 1, f"{method} {string}: {found}")
        match = re.search(r'invisible="([^"]*)"', found[0])
        return match.group(1) if match else None

    def test_12_document_view_has_one_button_per_type(self):
        expected = {
            "Download IVA voucher": "not has_emited_iva_retention",
            "Download ISLR voucher": "not has_emited_islr_retention",
            "Download municipal voucher": "not has_emited_municipal_retention",
        }
        for string, invisible in expected.items():
            self.assertEqual(
                self._button_invisible(
                    "account.move",
                    "account_move_form_l10n_ve_payment_extension",
                    "action_download_retention_voucher",
                    string,
                ),
                invisible,
            )
        _logger.info("========= test_12 passed =========")

    def test_13_retention_views_show_button_only_when_emitted(self):
        for view_xmlid in (
            "view_retention_iva_form_l10n_ve_payment_extension",
            "view_retention_islr_form_l10n_ve_payment_extension",
            "view_retention_municipal_form_l10n_ve_payment_extension",
        ):
            self.assertEqual(
                self._button_invisible(
                    "account.retention", view_xmlid, "action_print_retention_voucher_pdf"
                ),
                "state != 'emitted'",
            )
        _logger.info("========= test_13 passed =========")

    def test_14_municipal_view_matches_other_retention_forms(self):
        for view_xmlid in (
            "view_retention_iva_form_l10n_ve_payment_extension",
            "view_retention_islr_form_l10n_ve_payment_extension",
            "view_retention_municipal_form_l10n_ve_payment_extension",
        ):
            view = self.env.ref(f"l10n_ve_payment_extension.{view_xmlid}")
            arch = self.env["account.retention"].get_view(view.id)["arch"]
            self.assertIn("<sheet", arch, view_xmlid)
            self.assertIn("<chatter", arch, view_xmlid)
            self.assertIn('duplicate="false"', arch, view_xmlid)
        _logger.info("========= test_14 passed =========")

    def _from_invoice_context(self, move):
        return {
            "active_model": "account.move",
            "active_id": move.id,
            "active_ids": move.ids,
        }

    def _assert_report_context_is_retention(self, action, retentions):
        context = action["context"]
        self.assertEqual(context["active_model"], "account.retention")
        self.assertEqual(sorted(context["active_ids"]), sorted(retentions.ids))
        # l10n_ve_invoice reads active_model/active_ids from the report data: with
        # account.move the retention ids would be taken as invoice ids.
        html = self.env["ir.actions.report"]._render_qweb_html(
            REPORT_REF, retentions.ids, data={"context": context}
        )
        self.assertTrue(html)

    def test_15_retention_button_opened_from_invoice_uses_retention_model(self):
        for retention_type in TYPES:
            retention = self._create_retention(retention_type)
            move = retention.retention_line_ids.move_id
            action = retention.with_context(
                **self._from_invoice_context(move)
            ).action_print_retention_voucher_pdf()
            self._assert_report_context_is_retention(action, retention)
        _logger.info("========= test_15 passed =========")

    def test_16_document_button_from_invoice_uses_retention_model(self):
        for retention_type in TYPES:
            retention = self._create_retention(retention_type)
            move = retention.retention_line_ids.move_id
            action = move.with_context(
                retention_type=retention_type, **self._from_invoice_context(move)
            ).action_download_retention_voucher()
            self._assert_report_context_is_retention(action, retention)
        _logger.info("========= test_16 passed =========")
