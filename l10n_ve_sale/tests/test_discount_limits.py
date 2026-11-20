from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged
from odoo.tools import formatLang

from .test_discount_schemes import TestDiscountSchemes


@tagged("post_install", "-at_install", "l10n_ve_sale_discount")
class TestDiscountLimits(TestDiscountSchemes):
    """Allowed methods, maximum discount and approval of the excess."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.global_discount_account_id = cls.global_account
        base_groups = [
            "sales_team.group_sale_salesman_all_leads",
            "sale.group_discount_per_so_line",
            "account.group_account_invoice",
        ]

        def make_user(login, extra=()):
            groups = cls.env["res.groups"]
            for xmlid in list(base_groups) + list(extra):
                groups |= cls.env.ref(xmlid)
            return cls.env["res.users"].create(
                {
                    "name": login,
                    "login": login,
                    "company_id": cls.company.id,
                    "company_ids": [Command.set(cls.company.ids)],
                    "group_ids": [Command.set(groups.ids)],
                }
            )

        cls.seller = make_user("discount_seller")
        cls.approver = make_user("discount_approver", ["l10n_ve_sale.group_discount_approver"])

    def _limits(self, **extra):
        values = {
            "discount_max_limit_enabled": True,
            "discount_max_line": 10.0,
            "discount_max_global_subtotal": 10.0,
            "discount_max_global_total": 10.0,
        }
        values.update(extra)
        self.company.write(values)

    def test_no_limits_no_approval(self):
        order = self._order()
        self._wizard(order, "lines", "percent", 50).action_apply()
        self.assertFalse(order.discount_approval_state)

    def test_excess_is_refused_without_approval_setting(self):
        self._limits(discount_approval_enabled=False)
        order = self._order()
        with self.assertRaises(UserError):
            self._wizard(order, "lines", "percent", 20).action_apply()

    def test_excess_is_only_marked_then_confirming_sends_it_to_approval(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 20).with_user(self.seller).action_apply()
        # applying never moves the order: it is only marked
        self.assertEqual(order.discount_approval_state, "exceeds")
        self.assertEqual(order.state, "draft")
        # confirming does not confirm: it goes to the approval stage
        order.action_confirm()
        self.assertEqual(order.state, "to_approve")
        self.assertEqual(order.discount_approval_state, "to_approve")
        with self.assertRaises(UserError):  # waiting for the approver
            order.action_confirm()
        with self.assertRaises(UserError):  # a seller cannot approve
            order.with_user(self.seller).action_approve_discount()
        # approving takes it to the natural stage of Odoo: Sales Order
        order.with_user(self.approver).action_approve_discount()
        self.assertEqual(order.discount_approval_state, "approved")
        self.assertEqual(order.state, "sale")

    def test_approver_never_enters_the_stage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.approver)
        self._wizard(order, "lines", "percent", 20).with_user(self.approver).action_apply()
        self.assertFalse(order.discount_approval_state)

    def test_within_limit_does_not_need_approval(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 10).with_user(self.seller).action_apply()
        self.assertFalse(order.discount_approval_state)

    def test_fixed_amount_is_compared_as_percentage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "amount", 200).with_user(self.seller).action_apply()
        self.assertEqual(order.discount_approval_state, "exceeds")

    def test_global_total_limit(self):
        self._limits(discount_approval_enabled=True, discount_max_global_total=5.0)
        order = self._order().with_user(self.seller)
        self._wizard(order, "global_total", "percent", 10).with_user(self.seller).action_apply()
        self.assertEqual(order.discount_approval_state, "exceeds")

    def test_removing_the_discount_clears_the_stage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        wizard = self._wizard(order, "lines", "percent", 20).with_user(self.seller)
        wizard.action_apply()
        wizard.action_remove()
        self.assertFalse(order.discount_approval_state)

    def test_reject_removes_discount(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 20).with_user(self.seller).action_apply()
        order.action_confirm()
        order.with_user(self.approver).action_reject_discount()
        self.assertFalse(order.discount_approval_state)
        self.assertFalse(order.discount_mode)
        self.assertEqual(order.order_line.discount, 0.0)

    def test_unticked_method_cannot_be_applied_by_anyone(self):
        self.company.write({"discount_method_limit_enabled": True, "discount_allow_line_amount": False})
        for user in (self.seller, self.approver, self.env.user):
            with self.subTest(user=user.login):
                order = self._order().with_user(user)
                with self.assertRaises(UserError):
                    self._wizard(order, "lines", "amount", 50).with_user(user).action_apply()
        # a ticked method keeps working for everybody
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 5).with_user(self.seller).action_apply()
        self.assertEqual(order.discount_mode, "line_percent")

    def test_unticked_method_is_also_refused_when_typed_on_a_line(self):
        self.company.write({"discount_method_limit_enabled": True, "discount_allow_line_percent": False})
        order = self._order().with_user(self.seller)
        with self.assertRaises(UserError):
            order.order_line.write({"discount": 5.0})

    def test_method_limit_off_allows_every_method(self):
        self.company.write({"discount_method_limit_enabled": False, "discount_allow_line_amount": False})
        order = self._order()
        self._wizard(order, "lines", "amount", 50).action_apply()
        self.assertEqual(order.discount_mode, "line_amount")

    def test_maximum_applies_even_if_the_method_limit_is_off(self):
        self.company.discount_method_limit_enabled = False
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        self.assertEqual(order.discount_approval_state, "exceeds")

    def test_method_limit_does_not_limit_the_maximum(self):
        """Method limit on with every method ticked and the maximum off: any
        amount of discount is accepted."""
        self.company.discount_method_limit_enabled = True
        self.company.discount_max_limit_enabled = False
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 60).with_user(self.seller).action_apply()
        self.assertFalse(order.discount_approval_state)

    def test_method_limit_and_maximum_are_independent(self):
        """Method limit on (percentage not ticked) and maximum on: the percentage
        is refused for its method; a fixed amount over the maximum goes to approval."""
        self.company.write({"discount_method_limit_enabled": True, "discount_allow_line_percent": False})
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        with self.assertRaises(UserError):
            self._wizard(order, "lines", "percent", 5).with_user(self.seller).action_apply()
        self._wizard(order, "lines", "amount", 300).with_user(self.seller).action_apply()
        self.assertEqual(order.discount_approval_state, "exceeds")

    def test_manual_line_discount_is_also_limited(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        order.order_line.write({"discount": 30.0})
        self.assertEqual(order.discount_approval_state, "exceeds")

    def test_invoice_exceeding_goes_to_approval_when_posted_and_approving_posts_it(self):
        self._limits(discount_approval_enabled=True)
        order = self._order()
        order.action_confirm()
        invoice = order._create_invoices()
        invoice = invoice.with_user(self.seller).with_context(move_action_post_alert=True)
        self._wizard(invoice, "lines", "percent", 20).with_user(self.seller).action_apply()
        self.assertEqual(invoice.discount_approval_state, "exceeds")
        invoice.action_post()  # does not post: goes to approval
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.discount_approval_state, "to_approve")
        with self.assertRaises(UserError):  # no other path posts it either
            invoice._post()
        invoice.with_user(self.approver).action_approve_discount()
        self.assertEqual(invoice.state, "posted")

    # ------------------------------------------------------------------
    # Invoices follow the same flow as the orders
    # ------------------------------------------------------------------
    def _invoice_of_an_approved_order(self):
        """An order confirmed through the approval, and its draft invoice."""
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_approve_discount()
        self.assertEqual(order.state, "sale")
        invoice = order._create_invoices()
        self.assertEqual(invoice.discount_mode, "line_percent")
        self.assertFalse(invoice.discount_approval_state)
        return invoice

    def test_invoice_of_an_approved_order_is_not_asked_again(self):
        invoice = self._invoice_of_an_approved_order()
        invoice.with_user(self.seller).with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

    def test_same_or_lower_discount_applied_again_is_not_asked_again(self):
        invoice = self._invoice_of_an_approved_order().with_user(self.seller)
        for percent in (30, 20):
            with self.subTest(percent=percent):
                invoice._remove_discount()
                self._wizard(invoice, "lines", "percent", percent).with_user(self.seller).action_apply()
                self.assertFalse(invoice.discount_approval_state)

    def test_higher_discount_than_the_order_is_asked_again(self):
        invoice = self._invoice_of_an_approved_order().with_user(self.seller)
        invoice._remove_discount()
        self._wizard(invoice, "lines", "percent", 40).with_user(self.seller).action_apply()
        self.assertEqual(invoice.discount_approval_state, "exceeds")

    def test_other_scheme_than_the_order_is_asked_again(self):
        invoice = self._invoice_of_an_approved_order().with_user(self.seller)
        invoice._remove_discount()
        self._wizard(invoice, "global_subtotal", "percent", 30).with_user(self.seller).action_apply()
        self.assertEqual(invoice.discount_approval_state, "exceeds")

    def _invoice_in_the_stage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order()
        order.action_confirm()
        invoice = order._create_invoices().with_user(self.seller)
        self._wizard(invoice, "lines", "percent", 30).with_user(self.seller).action_apply()
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.discount_approval_state, "to_approve")
        return invoice

    def test_invoice_in_the_stage_is_locked(self):
        invoice = self._invoice_in_the_stage()
        with self.assertRaises(UserError):
            invoice.write({"ref": "changed"})
        with self.assertRaises(UserError):
            invoice.invoice_line_ids.write({"quantity": 5})
        with self.assertRaises(UserError):
            invoice.invoice_line_ids[:1].unlink()
        with self.assertRaises(UserError):
            invoice.unlink()

    def test_invoice_discount_column_respects_the_company_setting(self):
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        self.assertIn("not parent.show_discount_on_moves", arch)
        self.company.show_discount_on_moves = True
        move = self.env["account.move"].create({"move_type": "out_invoice", "partner_id": self.partner.id})
        self.assertTrue(move.show_discount_on_moves)
        self.company.show_discount_on_moves = False
        move.invalidate_recordset(["show_discount_on_moves"])
        self.assertFalse(move.show_discount_on_moves)

    def test_settings_screen_shows_both_discount_settings_in_the_discount_block(self):
        arch = self.env["res.config.settings"].get_views([(False, "form")])["views"]["form"]["arch"]
        for name in ("discount_type", "show_discount_on_moves"):
            self.assertEqual(arch.count('name="%s"' % name), 1, name)

    def test_invoice_in_the_stage_form_is_read_only(self):
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        self.assertIn("discount_approval_state == 'to_approve'", arch)

    def test_invoice_in_the_stage_can_be_cancelled_and_restarts(self):
        invoice = self._invoice_in_the_stage()
        invoice.button_cancel()
        self.assertEqual(invoice.state, "cancel")
        self.assertFalse(invoice.discount_approval_state)

    def test_invoice_approvers_are_notified_and_rejecting_removes_the_discount(self):
        invoice = self._invoice_in_the_stage()
        message = invoice.message_ids.filtered(
            lambda m: m.message_type == "comment" and "waiting for the approval" in (m.body or "")
        )[:1]
        self.assertIn(self.approver.partner_id, message.partner_ids)
        invoice.with_user(self.approver).action_reject_discount()
        self.assertFalse(invoice.discount_mode)
        self.assertEqual(invoice.state, "draft")
        self.assertFalse(invoice.discount_approval_state)

    # ------------------------------------------------------------------
    # The limits cannot be skipped from a client (RPC)
    # ------------------------------------------------------------------
    def _seller_order(self):
        self._limits(discount_approval_enabled=True)
        return self._order().with_user(self.seller)

    def test_seller_cannot_write_the_approval_state(self):
        order = self._seller_order()
        for state in ("approved", False):
            with self.subTest(state=state), self.assertRaises(AccessError):
                order.write({"discount_approval_state": state})

    def test_seller_cannot_write_the_scheme_by_hand(self):
        order = self._seller_order()
        for vals in (
            {"discount_mode": "global_total"},
            {"global_discount_type": "percent", "global_discount_percent": 100.0},
            {"global_discount_amount": 500.0},
        ):
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                order.write(vals)
        self.assertFalse(order.discount_mode)

    def test_client_context_key_does_not_skip_the_limit(self):
        order = self._seller_order()
        order.with_context(l10n_ve_discount_apply=True).order_line.write({"discount": 90.0})
        self.assertEqual(order.discount_approval_state, "exceeds")

    def test_seller_cannot_create_with_a_scheme(self):
        self._limits()
        with self.assertRaises(AccessError):
            self.env["sale.order"].with_user(self.seller).create(
                {"partner_id": self.partner.id, "discount_mode": "global_total"}
            )

    def test_invoice_scheme_fields_are_protected_too(self):
        self._limits(discount_approval_enabled=True)
        order = self._order()
        order.action_confirm()
        invoice = order._create_invoices().with_user(self.seller)
        with self.assertRaises(AccessError):
            invoice.write({"discount_approval_state": "approved"})
        invoice.with_context(l10n_ve_discount_apply=True).invoice_line_ids.write({"discount": 90.0})
        self.assertEqual(invoice.discount_approval_state, "exceeds")

    def test_duplicate_keeps_the_scheme(self):
        order = self._order()
        self._wizard(order, "lines", "percent", 10).action_apply()
        copy = order.with_user(self.seller).copy()
        self.assertEqual(copy.discount_mode, "line_percent")
        self.assertEqual(copy.order_line.discount, 10.0)

    # ------------------------------------------------------------------
    # 'To Approve' is a real stage of the order
    # ------------------------------------------------------------------
    def test_to_approve_is_a_stage_between_quotation_and_sale(self):
        keys = [key for key, _label in self.env["sale.order"]._fields["state"].selection]
        self.assertLess(keys.index("sent"), keys.index("to_approve"))
        self.assertLess(keys.index("to_approve"), keys.index("sale"))

    def test_confirming_an_excess_moves_the_order_to_the_stage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        self.assertEqual(order.state, "draft")
        order.action_confirm()
        self.assertEqual(order.state, "to_approve")
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_approver_never_enters_the_stage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.approver)
        self._wizard(order, "lines", "percent", 30).with_user(self.approver).action_apply()
        self.assertEqual(order.state, "draft")

    def test_approving_confirms_the_order(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        order.action_confirm()
        order.with_user(self.approver).action_approve_discount()
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.discount_approval_state, "approved")

    def _order_by(self, user, price=1000.0):
        """An order created by `user` (so they are its salesperson and creator)."""
        return self.env["sale.order"].with_user(user).create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "product_uom_qty": 1,
                            "price_unit": price,
                            "tax_ids": [Command.set(self.tax.ids)],
                        }
                    )
                ],
            }
        )

    def _order_in_the_stage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order_by(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        order.action_confirm()
        self.assertEqual(order.state, "to_approve")
        return order

    def _approval_message(self, order):
        return order.message_ids.filtered(
            lambda m: m.message_type == "comment" and "waiting for the approval" in (m.body or "")
        )[:1]

    def test_approvers_are_notified_when_the_order_enters_the_stage(self):
        order = self._order_in_the_stage()
        message = self._approval_message(order)
        self.assertTrue(message)
        self.assertIn(self.approver.partner_id, message.partner_ids)
        self.assertNotIn(self.seller.partner_id, message.partner_ids)
        self.assertTrue(
            message.notification_ids.filtered(lambda n: n.res_partner_id == self.approver.partner_id)
        )

    def _decision_message(self, order, word):
        return order.message_ids.filtered(
            lambda m: m.message_type == "comment" and word in (m.body or "")
        )[:1]

    def test_the_owner_is_notified_when_the_discount_is_approved(self):
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_approve_discount()
        message = self._decision_message(order, "was approved by")
        self.assertTrue(message)
        self.assertIn(self.seller.partner_id, message.partner_ids)
        self.assertNotIn(self.approver.partner_id, message.partner_ids)
        self.assertTrue(
            message.notification_ids.filtered(lambda n: n.res_partner_id == self.seller.partner_id)
        )

    def test_the_owner_is_notified_when_the_discount_is_rejected(self):
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_reject_discount()
        message = self._decision_message(order, "was rejected by")
        self.assertTrue(message)
        self.assertIn(self.seller.partner_id, message.partner_ids)

    def test_the_salesperson_and_the_creator_are_both_notified(self):
        order = self._order_in_the_stage()
        other = self.env["res.users"].create(
            {
                "name": "Other salesperson",
                "login": "other_discount_salesperson",
                "company_id": self.company.id,
                "company_ids": [Command.set(self.company.ids)],
                "group_ids": [Command.set(self.seller.group_ids.ids)],
            }
        )
        order.sudo().user_id = other
        order.with_user(self.approver).action_approve_discount()
        message = self._decision_message(order, "was approved by")
        self.assertIn(other.partner_id, message.partner_ids)
        self.assertIn(self.seller.partner_id, message.partner_ids)  # the creator

    def test_an_owner_who_approves_is_not_notified_of_it(self):
        """The approver who is also the owner is the one deciding: no message."""
        self._limits(discount_approval_enabled=True)
        order = self._order_by(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        order.action_confirm()
        order.sudo().write({"user_id": self.approver.id})  # the creator stays the seller
        order.with_user(self.approver).action_approve_discount()
        message = self._decision_message(order, "was approved by")
        self.assertNotIn(self.approver.partner_id, message.partner_ids)

    def test_each_approver_gets_a_todo_that_closes_when_approved(self):
        order = self._order_in_the_stage()
        todos = order.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref("l10n_ve_sale.mail_activity_type_discount_approval")
        )
        self.assertEqual(todos.user_id, self.approver)
        order.with_user(self.approver).action_approve_discount()
        self.assertFalse(
            order.activity_ids.filtered(
                lambda a: a.activity_type_id == self.env.ref("l10n_ve_sale.mail_activity_type_discount_approval")
            )
        )

    def test_every_approver_is_notified(self):
        group = self.env.ref("l10n_ve_sale.group_discount_approver")
        second = self.env["res.users"].create(
            {
                "name": "Second approver",
                "login": "second_discount_approver",
                "company_id": self.company.id,
                "company_ids": [Command.set(self.company.ids)],
                "group_ids": [Command.set((self.approver.group_ids | group).ids)],
            }
        )
        order = self._order_in_the_stage()
        message = self._approval_message(order)
        self.assertIn(self.approver.partner_id, message.partner_ids)
        self.assertIn(second.partner_id, message.partner_ids)

    def test_no_approver_blocks_entering_the_stage(self):
        self._limits(discount_approval_enabled=True)
        group = self.env.ref("l10n_ve_sale.group_discount_approver")
        self.approver.write({"group_ids": [Command.unlink(group.id)]})
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        with self.assertRaisesRegex(UserError, "no discount approver"):
            order.action_confirm()
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.discount_approval_state, "exceeds")

    def test_back_to_quotation_starts_the_approval_over(self):
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_approve_discount()
        self.assertEqual(order.state, "sale")
        order.with_user(self.seller)._action_cancel()
        order.with_user(self.seller).action_draft()
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.discount_approval_state, "exceeds")
        order.with_user(self.seller).action_confirm()
        self.assertEqual(order.state, "to_approve")
        self.assertEqual(order.discount_approval_state, "to_approve")

    def test_cancelled_while_waiting_goes_to_approval_again_after_quotation(self):
        order = self._order_in_the_stage()
        order.with_user(self.seller)._action_cancel()
        self.assertFalse(order.discount_approval_state)
        order.with_user(self.seller).action_draft()
        self.assertEqual(order.discount_approval_state, "exceeds")
        order.with_user(self.seller).action_confirm()
        self.assertEqual(order.state, "to_approve")

    def test_the_stage_locks_the_order_and_its_lines(self):
        order = self._order_in_the_stage()
        other = self.env["res.partner"].create({"name": "Another customer"})
        for user in (self.seller, self.approver):
            with self.subTest(user=user.login):
                locked = order.with_user(user)
                with self.assertRaises(UserError):
                    locked.write({"partner_id": other.id})
                with self.assertRaises(UserError):
                    locked.order_line.write({"discount": 5.0})
                with self.assertRaises(UserError):
                    locked.order_line.write({"price_unit": 1.0})
                with self.assertRaises(UserError):
                    locked.order_line.unlink()
                with self.assertRaises(UserError):
                    locked.write({"state": "draft"})  # nor can it be unlocked by hand
                with self.assertRaises(UserError):
                    self.env["sale.order.line"].with_user(user).create(
                        {"order_id": order.id, "product_id": self.product_a.id, "product_uom_qty": 1}
                    )
        self.assertEqual(order.discount_approval_state, "to_approve")
        self.assertEqual(order.order_line.discount, 30.0)

    def test_the_locked_order_cannot_get_a_new_discount(self):
        order = self._order_in_the_stage()
        with self.assertRaises(UserError):
            self._wizard(order, "lines", "percent", 5).with_user(self.approver).action_apply()

    def test_the_locked_order_can_still_be_cancelled(self):
        order = self._order_in_the_stage()
        order.with_user(self.seller)._action_cancel()
        self.assertEqual(order.state, "cancel")

    def test_the_form_of_the_locked_order_is_read_only(self):
        order = self._order_in_the_stage()
        form = Form(order.with_user(self.seller))
        with self.assertRaises(AssertionError):
            form.partner_id = self.env["res.partner"].create({"name": "Another customer"})
        with self.assertRaises(AssertionError):
            form.client_order_ref = "changed"

    def test_the_form_of_a_normal_order_is_still_editable(self):
        order = self._order().with_user(self.seller)
        form = Form(order)
        form.client_order_ref = "editable"
        form.save()
        self.assertEqual(order.client_order_ref, "editable")

    def test_rejecting_unlocks_the_order(self):
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_reject_discount()
        self.assertEqual(order.state, "draft")
        order.with_user(self.seller).write({"client_order_ref": "free again"})
        self.assertEqual(order.client_order_ref, "free again")

    def test_lowering_before_confirming_clears_the_mark(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        self.assertEqual(order.discount_approval_state, "exceeds")
        order.order_line.write({"discount": 5.0})
        self.assertFalse(order.discount_approval_state)
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_rejecting_removes_the_discount_and_leaves_the_stage(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        self._wizard(order, "lines", "percent", 30).with_user(self.seller).action_apply()
        order.action_confirm()
        order.with_user(self.approver).action_reject_discount()
        self.assertEqual(order.state, "draft")
        self.assertFalse(order.discount_mode)

    def test_discount_approval_permission_is_apart_from_the_sales_role(self):
        """The permission has its own privilege (selector), apart from Sales:
        granting it never replaces the sales role of the user."""
        sales = self.env.ref("sales_team.res_groups_privilege_sales")
        approver = self.env.ref("l10n_ve_sale.group_discount_approver")
        self.assertNotEqual(approver.privilege_id, sales)
        self.assertFalse(self.env.ref("l10n_ve_sale.group_discount_method_changer", raise_if_not_found=False))

    # ------------------------------------------------------------------
    # The window (driven with Form, as the web client does)
    # ------------------------------------------------------------------
    def _discount_form(self, document, user=None):
        """The Discount window opened from the button of the document."""
        action = document.action_open_discount_wizard()
        wizard_model = self.env["l10n_ve.discount.wizard"]
        if user:
            wizard_model = wizard_model.with_user(user)
        return Form(wizard_model.with_context(**action["context"]))

    @staticmethod
    def _offered(form, field):
        return [key for key, _label in form._view["fields"][field]["selection"]]

    def test_button_is_hidden_when_no_method_is_allowed(self):
        order = self._order()
        self.company.discount_method_limit_enabled = True
        self.assertTrue(order.discount_methods_available)
        for flag in (
            "discount_allow_line_percent",
            "discount_allow_line_amount",
            "discount_allow_global_subtotal",
            "discount_allow_global_total",
        ):
            self.company[flag] = False
        order.invalidate_recordset(["discount_methods_available"])
        self.assertFalse(order.discount_methods_available)
        view = self.env["sale.order"].get_view(
            self.env.ref("sale.view_order_form").id, "form"
        )
        self.assertIn("discount_methods_available", view["arch"])
        self.company.discount_method_limit_enabled = False
        order.invalidate_recordset(["discount_methods_available"])
        self.assertTrue(order.discount_methods_available)

    def test_form_offers_everything_when_the_method_is_not_limited(self):
        self.company.discount_method_limit_enabled = False
        form = self._discount_form(self._order())
        self.assertEqual(self._offered(form, "scheme"), ["lines", "global_subtotal", "global_total"])
        for scheme in ("lines", "global_subtotal", "global_total"):
            self.assertEqual(self._offered(form, "type_%s" % scheme), ["percent", "amount"])

    def test_form_ignores_the_ticks_when_the_method_is_not_limited(self):
        self.company.write({"discount_method_limit_enabled": False, "discount_allow_line_percent": False})
        form = self._discount_form(self._order())
        self.assertEqual(self._offered(form, "type_lines"), ["percent", "amount"])

    def test_form_hides_the_unticked_type_of_a_scheme(self):
        self.company.write({"discount_method_limit_enabled": True, "discount_allow_line_percent": False})
        form = self._discount_form(self._order())
        self.assertEqual(self._offered(form, "type_lines"), ["amount"])
        # the other schemes keep both types, and every scheme is still offered
        self.assertEqual(self._offered(form, "type_global_subtotal"), ["percent", "amount"])
        self.assertEqual(self._offered(form, "scheme"), ["lines", "global_subtotal", "global_total"])

    def test_form_hides_a_scheme_with_no_allowed_type(self):
        self.company.write(
            {
                "discount_method_limit_enabled": True,
                "discount_allow_line_percent": False,
                "discount_allow_line_amount": False,
                "discount_allow_global_total": False,
            }
        )
        form = self._discount_form(self._order())
        self.assertEqual(self._offered(form, "scheme"), ["global_subtotal"])
        self.assertEqual(form.scheme, "global_subtotal")

    def test_form_defaults_to_an_allowed_option(self):
        self.company.write({"discount_method_limit_enabled": True, "discount_allow_line_percent": False})
        form = self._discount_form(self._order())
        self.assertEqual(form.scheme, "lines")
        self.assertEqual(form.type_lines, "amount")

    def test_form_shows_the_type_of_the_chosen_scheme_only(self):
        form = self._discount_form(self._order())
        form.scheme = "global_total"
        form.type_global_total = "amount"
        with self.assertRaises(AssertionError):  # invisible for this scheme
            form.type_lines = "percent"

    def test_form_salesperson_applies_a_discount_from_the_button(self):
        order = self._order().with_user(self.seller)
        form = self._discount_form(order, user=self.seller)
        form.scheme = "global_subtotal"
        form.type_global_subtotal = "percent"
        form.value = 5
        form.save().action_apply()
        self.assertEqual(order.discount_mode, "global_subtotal")
        self.assertAlmostEqual(order.global_discount_percent, 5.0)

    def test_form_exceeding_the_maximum_marks_it_and_confirming_sends_it_to_approval(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.seller)
        form = self._discount_form(order, user=self.seller)
        form.scheme = "lines"
        form.type_lines = "percent"
        form.value = 20
        form.save().action_apply()
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.discount_approval_state, "exceeds")
        order.action_confirm()
        self.assertEqual(order.state, "to_approve")
        self.assertEqual(order.discount_approval_state, "to_approve")

    def test_form_unticked_type_is_refused_even_if_it_is_forced(self):
        """The window hides it, and the server refuses it anyway (RPC)."""
        self.company.write({"discount_method_limit_enabled": True, "discount_allow_line_percent": False})
        order = self._order().with_user(self.seller)
        wizard = self.env["l10n_ve.discount.wizard"].with_user(self.seller).create(
            {
                "res_model": "sale.order",
                "res_id": order.id,
                "scheme": "lines",
                "discount_type": "percent",
                "value": 5,
            }
        )
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_without_approval_the_maximum_is_an_error_even_for_an_approver(self):
        self._limits(discount_approval_enabled=False)
        order = self._order().with_user(self.approver)
        with self.assertRaises(UserError):
            self._wizard(order, "lines", "percent", 20).with_user(self.approver).action_apply()

    def test_with_approval_an_approver_exceeds_without_stopping(self):
        self._limits(discount_approval_enabled=True)
        order = self._order().with_user(self.approver)
        self._wizard(order, "lines", "percent", 20).with_user(self.approver).action_apply()
        self.assertFalse(order.discount_approval_state)
        self.assertEqual(order.order_line.discount, 20.0)

    def test_invoice_back_to_draft_starts_the_approval_over(self):
        invoice = self._invoice_in_the_stage()
        invoice.with_user(self.approver).action_approve_discount()
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")
        invoice.button_draft()
        self.assertEqual(invoice.state, "draft")
        # the order carried no discount, so the invoice one is not covered by it
        self.assertNotEqual(invoice.discount_approval_state, "to_approve")
        self.assertNotEqual(invoice.discount_approval_state, "approved")

    def test_invoice_cancelled_while_marked_clears_the_mark(self):
        self._limits(discount_approval_enabled=True)
        order = self._order()
        order.action_confirm()
        invoice = order._create_invoices().with_user(self.seller)
        self._wizard(invoice, "lines", "percent", 30).with_user(self.seller).action_apply()
        self.assertEqual(invoice.discount_approval_state, "exceeds")
        invoice.button_cancel()
        self.assertFalse(invoice.discount_approval_state)

    def test_invoice_activity_of_the_approvers_closes_when_approved(self):
        invoice = self._invoice_in_the_stage()
        todo = invoice.activity_ids.filtered(lambda a: a.user_id == self.approver)
        self.assertTrue(todo)
        invoice.with_user(self.approver).action_approve_discount()
        self.assertFalse(invoice.activity_ids.filtered(lambda a: a.user_id == self.approver))

    def test_invoice_owner_is_notified_when_approved(self):
        self._limits(discount_approval_enabled=True)
        order = self._order_by(self.seller)
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.invoice_user_id, self.seller)
        self._wizard(invoice, "lines", "percent", 30).with_user(self.seller).action_apply()
        invoice.with_user(self.seller).with_context(move_action_post_alert=True).action_post()
        invoice.with_user(self.approver).action_approve_discount()
        message = invoice.message_ids.filtered(
            lambda m: m.message_type == "comment" and "was approved by" in (m.body or "")
        )[:1]
        self.assertTrue(message)
        self.assertIn(self.seller.partner_id, message.partner_ids)

    # ------------------------------------------------------------------
    # Invoice: one single status bar
    # ------------------------------------------------------------------
    def test_invoice_stage_follows_the_state_and_the_approval(self):
        self._limits(discount_approval_enabled=True)
        order = self._order()
        order.action_confirm()
        invoice = order._create_invoices().with_user(self.seller)
        self.assertEqual(invoice.discount_stage, "draft")
        self._wizard(invoice, "lines", "percent", 30).with_user(self.seller).action_apply()
        self.assertEqual(invoice.discount_stage, "draft")  # marked, not waiting yet
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.discount_stage, "to_approve")
        invoice.with_user(self.approver).action_approve_discount()
        self.assertEqual(invoice.discount_stage, "draft")
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.discount_stage, "posted")
        invoice.button_draft()
        invoice.button_cancel()
        self.assertEqual(invoice.discount_stage, "cancel")

    def test_invoice_form_has_a_single_status_bar_with_the_stage(self):
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        self.assertIn('name="discount_stage"', arch)
        self.assertIn("draft,to_approve,posted", arch)
        # the native bar stays hidden
        self.assertRegex(
            arch, r'<field name="state"[^>]*widget="statusbar"[^>]*invisible="1"'
        )

    # ------------------------------------------------------------------
    # The approval lock never turns a read-only field editable
    # ------------------------------------------------------------------
    def test_lock_leaves_natively_read_only_fields_alone(self):
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        import re

        node = re.search(r'<field name="amount_residual"[^>]*>', arch).group(0)
        self.assertNotIn("readonly", node)
        editable = re.search(r'<field name="partner_id"[^>]*>', arch).group(0)
        self.assertIn("discount_approval_state == 'to_approve'", editable)

    def test_lock_leaves_read_only_order_fields_alone(self):
        import re

        arch = self.env["sale.order"].get_view(
            self.env.ref("sale.view_order_form").id, "form"
        )["arch"]
        node = re.search(r'<field name="amount_total"[^>]*>', arch)
        if node:
            self.assertNotIn("readonly", node.group(0))
        partner = re.search(r'<field name="partner_id"[^>]*>', arch).group(0)
        self.assertIn("state == 'to_approve'", partner)

    def test_lock_is_server_side_for_the_invoice_lines_and_cancel_is_allowed(self):
        invoice = self._invoice_in_the_stage()
        with self.assertRaises(UserError):
            invoice.invoice_line_ids[:1].write({"price_unit": 1.0})
        with self.assertRaises(UserError):
            self.env["account.move.line"].with_user(self.seller).create(
                {
                    "move_id": invoice.id,
                    "product_id": self.product_a.id,
                    "quantity": 1,
                    "price_unit": 10,
                }
            )
        invoice.button_cancel()
        self.assertEqual(invoice.state, "cancel")

    # ------------------------------------------------------------------
    # Draft invoices keep their residual (it was stored as 0 and showed "Paid")
    # ------------------------------------------------------------------
    def _form_invoice(self, user=None, prices=(600.0, 600.0)):
        """A draft invoice made on the form as the screen does: the draft is
        saved first with its customer, the lines are added in a later save."""
        self.product_a.taxes_id = self.tax
        Move = self.env["account.move"].with_context(default_move_type="out_invoice")
        if user:
            Move = Move.with_user(user)
        with Form(Move) as form:
            form.partner_id = self.partner
        move = form.record
        with Form(move) as form:
            for price in prices:
                with form.invoice_line_ids.new() as line:
                    line.product_id = self.product_a
                    line.quantity = 1
                    line.price_unit = price
        self.env.flush_all()
        self.env.invalidate_all()
        return move

    def _apply_with_form(self, document, scheme, discount_type, value, user=None):
        """The Discount window of the button, filled and applied."""
        form = self._discount_form(document, user=user)
        form.scheme = scheme
        setattr(form, "type_%s" % scheme, discount_type)
        form.value = value
        form.save().action_apply()

    def _post_alert(self, move, user=None):
        """The posting alert the Confirm button opens, confirmed."""
        wizard = self.env["move.action.post.alert.wizard"]
        if user:
            wizard = wizard.with_user(user)
        form = Form(wizard.with_context(default_move_id=move.id))
        form.save().action_confirm()

    def _invoice_by_steps(self, discount=None):
        move = self._form_invoice()
        if discount:
            self._apply_with_form(move, "lines", "percent", discount)
        self.env.flush_all()
        self.env.invalidate_all()
        return move

    def test_draft_invoice_created_by_steps_keeps_its_residual(self):
        move = self._invoice_by_steps()
        self.assertAlmostEqual(move.amount_residual, move.amount_total, 2)
        self.assertGreater(move.amount_residual, 0)
        self.assertEqual(move.payment_state, "not_paid")

    def test_draft_invoice_residual_follows_the_discount(self):
        move = self._invoice_by_steps(discount=20)
        self.assertAlmostEqual(move.amount_total, 1113.6, 2)
        self.assertAlmostEqual(move.amount_residual, 1113.6, 2)
        self.assertEqual(move.payment_state, "not_paid")

    def test_draft_invoice_residual_follows_the_global_total_discount(self):
        move = self._invoice_by_steps()
        self._apply_with_form(move, "global_total", "percent", 10)
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertAlmostEqual(move.amount_total, 1392.0 * 0.9, 2)
        self.assertAlmostEqual(move.amount_residual, move.amount_total, 2)
        self.assertEqual(move.payment_state, "not_paid")

    def test_draft_invoice_totals_widget_in_company_currency_is_the_net_total(self):
        move = self._invoice_by_steps()
        self._apply_with_form(move, "global_total", "percent", 10)
        move.invalidate_recordset(["tax_totals"])
        totals = move.tax_totals
        self.assertEqual(totals["global_discount_mode"], "global_total")
        net = move.company_currency_id.round(1392.0 * 0.9)
        self.assertAlmostEqual(totals["total_amount_currency"], net, 2)
        self.assertEqual(
            totals["formatted_total_amount_currency_ves"],
            formatLang(self.env, net, currency_obj=move.company_currency_id),
        )

    def test_posted_invoice_total_in_company_currency_matches_its_entry(self):
        move = self._invoice_by_steps(discount=20)
        move.with_context(move_action_post_alert=True).action_post()
        move.invalidate_recordset(["tax_totals"])
        self.assertAlmostEqual(abs(move.amount_total_signed), 1113.6, 2)
        self.assertAlmostEqual(move.amount_residual, 1113.6, 2)

    # ------------------------------------------------------------------
    # Invoice flow driven with Form: confirm, stage, approve, alert, post
    # ------------------------------------------------------------------
    def _form_invoice_in_the_stage(self):
        """The seller builds the invoice on the form, applies an excess from the
        Discount window and presses Confirm: it waits for an approver."""
        self._limits(discount_approval_enabled=True)
        invoice = self._form_invoice(user=self.seller)
        self._apply_with_form(invoice, "lines", "percent", 30, user=self.seller)
        self.assertEqual(invoice.discount_approval_state, "exceeds")
        answer = invoice.action_post()
        self.assertEqual(answer.get("tag"), "display_notification")
        self.assertEqual(invoice.discount_approval_state, "to_approve")
        return invoice

    def test_form_invoice_confirm_without_permission_goes_to_approval_without_the_alert(self):
        invoice = self._form_invoice_in_the_stage()
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.discount_stage, "to_approve")

    def test_form_invoice_within_the_limit_shows_the_alert_then_posts(self):
        self._limits(discount_approval_enabled=True)
        invoice = self._form_invoice(user=self.seller)
        self._apply_with_form(invoice, "lines", "percent", 5, user=self.seller)
        answer = invoice.action_post()
        self.assertEqual(answer["res_model"], "move.action.post.alert.wizard")
        self._post_alert(invoice, user=self.seller)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.discount_stage, "posted")

    def test_form_invoice_approver_confirming_an_excess_gets_the_alert_and_posts(self):
        self._limits(discount_approval_enabled=True)
        invoice = self._form_invoice(user=self.approver)
        self._apply_with_form(invoice, "lines", "percent", 30, user=self.approver)
        self.assertFalse(invoice.discount_approval_state)
        answer = invoice.action_post()
        self.assertEqual(answer["res_model"], "move.action.post.alert.wizard")
        self._post_alert(invoice, user=self.approver)
        self.assertEqual(invoice.state, "posted")

    def test_form_invoice_approving_returns_the_alert_and_confirming_it_posts(self):
        invoice = self._form_invoice_in_the_stage()
        answer = invoice.with_user(self.approver).action_approve_discount()
        self.assertEqual(invoice.discount_approval_state, "approved")
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(answer["res_model"], "move.action.post.alert.wizard")
        self._post_alert(invoice, user=self.approver)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total, 2)

    def test_form_invoice_non_approver_cannot_approve(self):
        invoice = self._form_invoice_in_the_stage()
        with self.assertRaises(UserError):
            invoice.with_user(self.seller).action_approve_discount()
        self.assertEqual(invoice.discount_approval_state, "to_approve")

    def test_form_invoice_no_approver_blocks_entering_the_stage(self):
        self._limits(discount_approval_enabled=True)
        self.env.ref("l10n_ve_sale.group_discount_approver").write({"user_ids": [Command.clear()]})
        invoice = self._form_invoice(user=self.seller)
        self._apply_with_form(invoice, "lines", "percent", 30, user=self.seller)
        with self.assertRaisesRegex(UserError, "no discount approver"):
            invoice.action_post()
        self.assertEqual(invoice.discount_approval_state, "exceeds")
        self.assertEqual(invoice.discount_stage, "draft")

    def test_form_invoice_in_the_stage_cannot_be_edited_on_the_form(self):
        """The form itself is read-only in the stage (the Form of the test follows
        the view modifiers like the web client); the server refuses it as well."""
        invoice = self._form_invoice_in_the_stage()
        with self.assertRaises(AssertionError):
            with Form(invoice) as form:
                form.ref = "changed"
        with self.assertRaises(AssertionError):
            with Form(invoice) as form:
                with form.invoice_line_ids.edit(0) as line:
                    line.price_unit = 1.0
        with self.assertRaises(UserError):
            invoice.write({"ref": "changed"})

    def test_form_invoice_in_the_stage_can_be_cancelled(self):
        invoice = self._form_invoice_in_the_stage()
        invoice.button_cancel()
        self.assertEqual(invoice.state, "cancel")
        self.assertFalse(invoice.discount_approval_state)
        self.assertEqual(invoice.discount_stage, "cancel")

    def test_form_invoice_rejecting_removes_the_discount_and_unlocks_it(self):
        invoice = self._form_invoice_in_the_stage()
        invoice.with_user(self.approver).action_reject_discount()
        self.assertFalse(invoice.discount_mode)
        self.assertEqual(invoice.discount_stage, "draft")
        with Form(invoice) as form:
            form.ref = "editable again"
        self.assertEqual(invoice.ref, "editable again")

    def test_form_invoice_of_an_approved_order_is_posted_without_asking_again(self):
        self._limits(discount_approval_enabled=True)
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_approve_discount()
        invoice = order._create_invoices().with_user(self.seller)
        answer = invoice.action_post()
        self.assertEqual(answer["res_model"], "move.action.post.alert.wizard")
        self._post_alert(invoice, user=self.seller)
        self.assertEqual(invoice.state, "posted")

    def test_form_invoice_discount_removed_and_a_bigger_one_applied_asks_again(self):
        self._limits(discount_approval_enabled=True)
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_approve_discount()
        invoice = order._create_invoices().with_user(self.seller)
        invoice._remove_discount()
        self._apply_with_form(invoice, "lines", "percent", 40, user=self.seller)
        self.assertEqual(invoice.discount_approval_state, "exceeds")
        answer = invoice.action_post()
        self.assertEqual(answer.get("tag"), "display_notification")
        self.assertEqual(invoice.discount_stage, "to_approve")

    def test_form_invoice_discount_removed_and_the_same_one_applied_is_not_asked(self):
        self._limits(discount_approval_enabled=True)
        order = self._order_in_the_stage()
        order.with_user(self.approver).action_approve_discount()
        invoice = order._create_invoices().with_user(self.seller)
        invoice._remove_discount()
        self._apply_with_form(invoice, "lines", "percent", 30, user=self.seller)
        self.assertFalse(invoice.discount_approval_state)

    def test_form_invoice_back_to_draft_starts_the_approval_over(self):
        invoice = self._form_invoice_in_the_stage()
        invoice.with_user(self.approver).action_approve_discount()
        self._post_alert(invoice, user=self.approver)
        self.assertEqual(invoice.state, "posted")
        invoice.button_draft()
        self.assertEqual(invoice.state, "draft")
        self.assertNotEqual(invoice.discount_approval_state, "to_approve")
        self.assertNotEqual(invoice.discount_approval_state, "approved")

    def test_form_invoice_residual_is_kept_while_editing_the_discount(self):
        invoice = self._form_invoice()
        for percent, expected in ((20, 1113.6), (10, 1252.8)):
            invoice._remove_discount()
            self._apply_with_form(invoice, "lines", "percent", percent)
            self.env.flush_all()
            self.env.invalidate_all()
            self.assertAlmostEqual(invoice.amount_residual, expected, 2)
            self.assertEqual(invoice.payment_state, "not_paid")

    # ------------------------------------------------------------------
    # With IGTF installed (it reads the amounts of the invoice while its totals
    # are computed: the cycle that used to leave the draft residual at 0)
    # ------------------------------------------------------------------
    def test_form_invoice_residual_and_igtf_totals_in_draft(self):
        if "bi_igtf" not in self.env["account.move"]._fields:
            self.skipTest("l10n_ve_igtf is not installed")
        self.company.write({"igtf_percentage": 3.0, "show_igtf_suggested_account_move": True})
        invoice = self._form_invoice()
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total, 2)
        self.assertEqual(invoice.payment_state, "not_paid")
        for scheme, expected in (("lines", 1113.6), ("global_total", 1252.8)):
            invoice._remove_discount()
            value = 20 if scheme == "lines" else 10
            self._apply_with_form(invoice, scheme, "percent", value)
            self.env.flush_all()
            self.env.invalidate_all()
            self.assertAlmostEqual(invoice.amount_total, expected, 2)
            self.assertAlmostEqual(invoice.amount_residual, expected, 2)
            self.assertEqual(invoice.payment_state, "not_paid")
            totals = invoice.tax_totals
            self.assertAlmostEqual(totals["amount_total_igtf"], expected * 1.03, 2)
