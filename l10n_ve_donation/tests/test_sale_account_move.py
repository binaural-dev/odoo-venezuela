from odoo import fields, Command
from odoo.tests import Form, tagged
from odoo.exceptions import ValidationError, UserError
from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'sale_account', '-at_install', 'post_install')
class TestSaleAccountMove(TestDonationCommon):

    def test_01_sale_order_donation_onchange(self):
        """Marking a SO as donation sets the document type and the donation
        warehouse -- the partner is NOT forced to the company anymore (it
        keeps representing the real beneficiary)."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        order.is_donation = True
        order._onchange_is_donation()
        self.assertEqual(order.partner_id, self.partner)
        self.assertEqual(order.document, "invoice")
        self.assertEqual(order.warehouse_id, self.warehouse_donation)

    def test_02_sale_order_donation_no_warehouse(self):
        """ValidationError if no donation warehouse exists."""
        self.warehouse_donation.write({"is_donation_warehouse": False})
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        order.is_donation = True
        with self.assertRaises(ValidationError):
            order._onchange_is_donation()
        self.warehouse_donation.write({"is_donation_warehouse": True})

    def test_03_sale_order_partner_change_donation(self):
        """A donation SO accepts any contact as customer -- it no longer has
        to be the company (the partner represents the real beneficiary, not
        a duplicate of the company). Built with `Form`, setting the real
        beneficiary as partner_id AFTER enabling the donation flag but still
        inside the same `Form` session, so this exercises the `onchange`
        chain (not a `write()`) -- this is what would catch a regression if
        `_onchange_partner_id_donation()` were ever reintroduced. Actually
        invoiced: the resulting invoice carries the real beneficiary as its
        partner_id, not the company."""
        # manually_set_rate/foreign_rate/foreign_inverse_rate are
        # invisible="1" in the form view (backend-only, not user-editable)
        # -- supplied via context defaults, same as Odoo itself would set
        # them from a non-UI flow, instead of writing them after save()
        # (triggers an unrelated pre-existing chatter-message bug in
        # l10n_ve_sale's write() override when these fields change via
        # write on an already-saved record).
        sale_order_model = self.env["sale.order"].with_context(
            default_manually_set_rate=True,
            default_foreign_rate=1.0,
            default_foreign_inverse_rate=1.0,
        )
        with Form(sale_order_model) as order_form:
            order_form.partner_id = self.company.partner_id
            with order_form.order_line.new() as line:
                line.product_id = self.product_donation
                line.product_uom_qty = 1
                line.price_unit = 100
            order_form.is_donation = True
            # The real beneficiary is set AFTER enabling the donation flag,
            # still inside the Form session so it goes through the onchange
            # chain -- no longer forced to the company.
            order_form.partner_id = self.partner
        order = order_form.save()
        self.assertEqual(order.document, "invoice")
        self.assertEqual(order.partner_id, self.partner)

        order.action_confirm()
        invoices = order._create_invoices()
        self.assertTrue(invoices)
        self.assertEqual(invoices.partner_id, self.partner)
        self.assertNotEqual(invoices.partner_id, self.company.partner_id)

    def test_04_sale_order_donation_constrain(self):
        """Cannot change is_donation on confirmed order."""
        order = self.env["sale.order"].create({
            "partner_id": self.company.partner_id.id,
            "is_donation": False,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
            "order_line": [Command.create({
                "product_id": self.product_donation.id,
                "product_uom_qty": 1,
                "price_unit": 100,
            })]
        })
        order.action_confirm()
        with self.assertRaises(ValidationError):
            order.write({"is_donation": True})

    def test_05_sale_order_prepare_invoice(self):
        """Invoice prepared from donation SO has is_donation=True."""
        order = self.env["sale.order"].create({
            "partner_id": self.company.partner_id.id,
            "is_donation": True,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
            "order_line": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 1,
                "price_unit": 100,
            })]
        })
        invoice_vals = order._prepare_invoice()
        self.assertTrue(invoice_vals.get("is_donation"))

    def test_06_account_move_check_partner_donation(self):
        """The HEADER partner (move.partner_id) of a donation move is no
        longer constrained to the company partner -- it represents the real
        counterparty. Changing it must not raise, as long as the
        LINES still use the company partner (see test_07, unchanged).

        Also confirms the combined behavior with the blocker fix: after
        action_post(), the header keeps the beneficiary and every line
        keeps the company (action_post()'s own line-forcing loop in
        l10n_ve_donation, untouched)."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100,
                    "credit": 0,
                    "partner_id": self.company.partner_id.id,
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0,
                    "credit": 100,
                    "partner_id": self.company.partner_id.id,
                }),
            ],
        })
        # Should not raise
        move._check_partner_donation()
        # Changing the HEADER partner must not raise anymore.
        move.partner_id = self.partner.id
        move._check_partner_donation()
        self.assertEqual(move.partner_id, self.partner)

        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.partner_id, self.partner)
        for line in move.line_ids:
            self.assertEqual(line.partner_id, self.company.partner_id)

    def test_07_account_move_check_line_partner_donation(self):
        """Line partner on donation move must be company partner."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100,
                    "credit": 0,
                    "partner_id": self.company.partner_id.id,
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0,
                    "credit": 100,
                    "partner_id": self.company.partner_id.id,
                }),
            ],
        })
        # Change line partner
        line = move.line_ids.filtered(lambda l: l.credit > 0)
        with self.assertRaises(ValidationError):
            line.partner_id = self.partner.id
            move._check_partner_donation()

    def test_08_account_move_post_donation_invoice(self):
        """Posting a donation out_invoice creates a credit note automatically."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "correlative": "99991",
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")
        # A credit note should exist
        credit_notes = self.env["account.move"].search([
            ("reversed_entry_id", "=", move.id),
        ])
        self.assertTrue(credit_notes)
        self.assertEqual(credit_notes[0].move_type, "out_refund")
        self.assertTrue(credit_notes[0].is_donation)

    def _create_donation_invoice_for_batch(self, correlative):
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "correlative": correlative,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })

    def test_08b_post_several_donation_invoices_at_once(self):
        """Posting several donation invoices in one call creates a credit
        note for each one of them (the loop must not stop at the first)."""
        invoices = (
            self._create_donation_invoice_for_batch("99981")
            | self._create_donation_invoice_for_batch("99982")
            | self._create_donation_invoice_for_batch("99983")
        )
        invoices.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(set(invoices.mapped("state")), {"posted"})
        for invoice in invoices:
            credit_notes = self.env["account.move"].search([("reversed_entry_id", "=", invoice.id)])
            self.assertEqual(len(credit_notes), 1, invoice.name)
            self.assertEqual(credit_notes.state, "posted")

    def test_08c_post_mixed_batch_of_donation_invoice_and_entry(self):
        """A batch with a donation invoice and a donation entry handles
        both: the credit note of the invoice and the partner of the lines
        of the entry."""
        invoice = self._create_donation_invoice_for_batch("99984")
        entry = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "ref": "Mixed Ref",
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 50, "credit": 0, "name": "Mixed 1",
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0, "credit": 50,
                }),
            ],
        })
        (invoice | entry).with_context(move_action_post_alert=True).action_post()
        self.assertTrue(self.env["account.move"].search([("reversed_entry_id", "=", invoice.id)]))
        self.assertEqual(entry.state, "posted")
        self.assertEqual(entry.line_ids.mapped("partner_id"), self.company.partner_id)

    def test_08d_post_again_does_not_reverse_a_posted_invoice_twice(self):
        invoice = self._create_donation_invoice_for_batch("99985")
        invoice.with_context(move_action_post_alert=True).action_post()
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(
            len(self.env["account.move"].search([("reversed_entry_id", "=", invoice.id)])), 1
        )

    def test_09_account_move_post_donation_entry(self):
        """Posting a donation entry updates line partners and names."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "ref": "Donation Ref",
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100,
                    "credit": 0,
                    "name": "Line 1",
                    "partner_id": self.company.partner_id.id,
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0,
                    "credit": 100,
                    "partner_id": self.company.partner_id.id,
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        for line in move.line_ids:
            self.assertEqual(line.partner_id, self.company.partner_id)
        # The reference of the entry is not appended to the label.
        debit_line = move.line_ids.filtered(lambda l: l.debit > 0)
        self.assertEqual(debit_line.name, "Line 1")

    def _entry_vals(self, journal=None, is_donation=True, ref="Entry Ref"):
        return {
            "move_type": "entry",
            "is_donation": is_donation,
            "journal_id": (journal or self.journal_general).id,
            "ref": ref,
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100, "credit": 0, "name": "Entry 1",
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0, "credit": 100,
                }),
            ],
        }

    def test_09a_lines_of_a_new_donation_entry_get_the_company_partner(self):
        """The partner is set while the entry is a draft, not when posted."""
        move = self.env["account.move"].create(self._entry_vals())
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.line_ids.mapped("partner_id"), self.company.partner_id)

    def test_09c_marking_an_existing_entry_as_donation_fills_the_partner(self):
        move = self.env["account.move"].create(self._entry_vals(is_donation=False))
        self.assertFalse(move.line_ids.mapped("partner_id"))
        move.is_donation = True
        self.assertEqual(move.line_ids.mapped("partner_id"), self.company.partner_id)

    def test_09f_lines_created_with_an_empty_partner_get_the_company_partner(self):
        """The web client sends `partner_id: False` in the lines it creates
        (a value in the creation values is not computed)."""
        vals = self._entry_vals()
        for command in vals["line_ids"]:
            command[2]["partner_id"] = False
        move = self.env["account.move"].create(vals)
        self.assertEqual(move.line_ids.mapped("partner_id"), self.company.partner_id)

        # Lines added later to the same draft entry.
        move.write({"line_ids": [
            Command.create({
                "account_id": self.account_expense.id, "debit": 10, "credit": 0, "partner_id": False,
            }),
            Command.create({
                "account_id": self.account_receivable.id, "debit": 0, "credit": 10, "partner_id": False,
            }),
        ]})
        self.assertEqual(move.line_ids.mapped("partner_id"), self.company.partner_id)

    def test_09g_partner_emptied_in_draft_is_filled_before_posting(self):
        move = self.env["account.move"].create(self._entry_vals())
        move.line_ids.partner_id = False
        self.assertFalse(move.line_ids.mapped("partner_id"))
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.line_ids.mapped("partner_id"), self.company.partner_id)

    def test_09d_regular_entry_lines_keep_no_partner(self):
        move = self.env["account.move"].create(self._entry_vals(is_donation=False))
        self.assertFalse(move.line_ids.mapped("partner_id"))

    def test_09e_posting_a_donation_entry_writes_nothing_on_its_lines(self):
        move = self.env["account.move"].create(self._entry_vals())
        lines_before = {line.id: (line.name, line.partner_id.id) for line in move.line_ids}
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(
            {line.id: (line.name, line.partner_id.id) for line in move.line_ids}, lines_before
        )

    def test_09b_post_donation_entry_in_a_hashed_journal(self):
        """A journal that locks the posted entries with a hash must still
        accept the donation entry: nothing is written on its lines when it
        is posted."""
        journal = self.env["account.journal"].create({
            "name": "Hashed Donation Journal",
            "code": "HDJ",
            "type": "general",
            "company_id": self.company.id,
            "restrict_mode_hash_table": True,
        })
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": journal.id,
            "ref": "Hashed Ref",
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100, "credit": 0, "name": "Hashed 1",
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0, "credit": 100,
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.line_ids.mapped("partner_id"), self.company.partner_id)

    def test_10_account_move_reverse_donation(self):
        """Reverse a donation invoice creates refund with donation lines."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "correlative": "99992",
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        # Reverse via wizard
        wizard = self.env["account.move.reversal"].with_context(
            active_ids=move.ids,
            active_model="account.move",
        ).create({
            "date": fields.Date.today(),
            "journal_id": move.journal_id.id,
        })
        wizard.reverse_moves()
        refund = wizard.new_move_ids
        self.assertTrue(refund)
        self.assertTrue(refund.is_donation)
        self.assertEqual(refund.move_type, "out_refund")

    def test_11_product_line_donation_no_product(self):
        """Error if no donation product configured."""
        self.product_donation.product_tmpl_id.write({"is_donation_product": False})
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })
        with self.assertRaises(UserError):
            move.product_line_donation()
        self.product_donation.product_tmpl_id.write({"is_donation_product": True})

    def test_12_product_line_donation_no_account(self):
        """Error if no donation account configured."""
        self.company.write({"donation_account_id": False})
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })
        with self.assertRaises(UserError):
            move.product_line_donation()
        self.company.write({"donation_account_id": self.account_expense.id})

    def test_13_get_tax_grouped_lines(self):
        """Tax grouping returns correct base amounts."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 2,
                    "price_unit": 50,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })
        groups = move._get_tax_grouped_lines()
        self.assertEqual(len(groups), 1)
        self.assertAlmostEqual(
            groups[tuple(sorted([self.sale_tax.id]))]["base_amount"],
            200.0,
            places=2,
        )

    def test_14_can_reverse_donation_move(self):
        """Field computed based on group."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
        })
        move._compute_can_reverse_donation_move()
        self.assertTrue(move.can_reverse_donation_move)

    def test_15_account_move_line_check_payable_receivable_donation(self):
        """Override allows expense account as payment_term for donation."""
        # Create a donation sale move manually with payment term line on expense account
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "correlative": "99993",
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })
        # After creation, find the payment term line and switch its account to expense (donation)
        pt_line = move.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        self.assertTrue(pt_line)
        pt_line.account_id = self.account_expense
        # Trigger the constrains manually to exercise the override
        pt_line._check_payable_receivable()
        # Posting should also succeed
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")

    def test_16_print_donation_certificate(self):
        """Print action returns an action dict."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                }),
            ],
        })
        action = move.print_donation_certificate()
        self.assertTrue(isinstance(action, dict))
        self.assertIn("type", action)

    def test_17_company_settings(self):
        """Company and settings fields are linked correctly (the stock
        journal is a core field of the company in V19: only the donation
        account is exposed by this module in the settings)."""
        self.assertEqual(self.company.donation_account_id, self.account_expense)
        self.assertEqual(self.company.account_stock_journal_id, self.journal_general)
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.donation_account_id, self.account_expense)

    def test_18_multi_company_warehouse_selection(self):
        """Sale Order MUST pick donation warehouse of the current company."""
        company_b = self.env["res.company"].create({"name": "Company B"})
        warehouse_b = self.env["stock.warehouse"].create({
            "name": "Donation WH B",
            "code": "DWHB",
            "company_id": company_b.id,
            "is_donation_warehouse": True,
        })

        partner_b = self.env["res.partner"].create({
            "name": "Test Partner B",
            "company_id": False,
        })

        order_a = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
        })
        order_a.is_donation = True
        order_a._onchange_is_donation()
        
        self.assertEqual(order_a.warehouse_id, self.warehouse_donation)
        self.assertNotEqual(order_a.warehouse_id, warehouse_b)

        order_b = self.env["sale.order"].with_company(company_b).create({
            "partner_id": partner_b.id,
            "company_id": company_b.id,
        })
        order_b.is_donation = True
        order_b._onchange_is_donation()

        self.assertEqual(order_b.warehouse_id, warehouse_b)
        self.assertNotEqual(order_b.warehouse_id, self.warehouse_donation)

    def test_19_certificate_shows_real_beneficiary(self):
        """The donation certificate (account.move) shows the real
        beneficiary's name/RIF in both mentions, not the company
        -- even though the print button is only shown for
        move_type == 'entry', the report itself is not restricted."""
        beneficiary = self.env["res.partner"].create({
            "name": "Fundación Beneficiaria Test",
            "vat": "J-12345678-9",
        })
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": beneficiary.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                }),
            ],
        })
        self.assertNotEqual(move.partner_id, self.company.partner_id)
        # `l10n_ve_invoice` only prints posted documents.
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")
        report = self.env.ref("l10n_ve_donation.action_donation_certificate_account_move")
        html, _report_type = report._render_qweb_html(report.report_name, move.ids)
        self.assertIn(beneficiary.name.encode(), html)
        self.assertIn(beneficiary.vat.encode(), html)

    def test_20_post_donation_invoice_stops_at_alert_wizard(self):
        """When `l10n_ve_accountant` answers with its alert wizard (an
        action dict), the donation flow does not run: the invoice stays in
        draft and no credit note is created until `action_post` is called
        again with `move_action_post_alert`."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.sale_tax.id])],
                }),
            ],
        })
        action = move.action_post()
        self.assertIsInstance(action, dict)
        self.assertEqual(action["res_model"], "move.action.post.alert.wizard")
        self.assertEqual(move.state, "draft")
        self.assertFalse(self.env["account.move"].search([("reversed_entry_id", "=", move.id)]))

        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")
        self.assertTrue(self.env["account.move"].search([("reversed_entry_id", "=", move.id)]))

    def test_21_is_donation_is_editable_on_new_manual_entry(self):
        """Manual donation entries (money donations) are marked by the
        user: the field must be visible and editable on a draft entry, and
        not editable on an invoice (those take the mark from the sale
        order)."""
        entry_form = Form(self.env["account.move"].with_context(default_move_type="entry"))
        entry_form.is_donation = True
        self.assertTrue(entry_form.is_donation)

        invoice_form = Form(self.env["account.move"].with_context(default_move_type="out_invoice"))
        with self.assertRaises(AssertionError):
            invoice_form.is_donation = True

    def _render_certificate(self, move):
        report = self.env.ref("l10n_ve_donation.action_donation_certificate_account_move")
        html, _report_type = report._render_qweb_html(report.report_name, move.ids)
        return html.decode()

    def test_22_certificate_of_a_money_entry_states_the_sum(self):
        """The certificate of a manual entry is the one of a money
        donation: it states the numeric sum, its equivalent in
        the alternate currency at the rate of the entry, and the concept;
        it does not talk about goods."""
        move = self.env["account.move"].create(self._entry_vals(ref="Aporte para el comedor"))
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")

        amounts = move._get_donation_certificate_amounts()
        self.assertEqual(amounts["currency"], self.company.currency_id)
        self.assertEqual(amounts["amount"], 100.0)
        self.assertEqual(amounts["equivalent_currency"], self.company.foreign_currency_id)
        self.assertEqual(amounts["equivalent_amount"], move.foreign_debit)
        self.assertEqual(amounts["rate"], move.foreign_rate)

        html = self._render_certificate(move)
        self.assertIn("la suma de", html)
        # The sum is numeric (no amount in words) and the rate shows 4 decimals.
        self.assertNotIn(amounts["currency"].amount_to_text(amounts["amount"]), html)
        rate_html = self.env["ir.qweb.field.float"].value_to_html(amounts["rate"], {"precision": 4})
        self.assertIn(rate_html, html)
        self.assertNotIn(self.env["ir.qweb.field.float"].value_to_html(amounts["rate"], {"precision": 6}), html)
        self.assertIn("equivalente a", html)
        self.assertIn("tasa BCV", html)
        self.assertIn("Aporte para el comedor", html)
        self.assertNotIn("bienes", html)

    def test_23_certificate_without_alternate_amount_omits_the_equivalent(self):
        move = self.env["account.move"].create(self._entry_vals())
        move.foreign_currency_id = self.company.currency_id
        move.with_context(move_action_post_alert=True).action_post()
        amounts = move._get_donation_certificate_amounts()
        self.assertFalse(amounts["equivalent_currency"])
        self.assertEqual(amounts["equivalent_amount"], 0.0)

        html = self._render_certificate(move)
        self.assertIn("la suma de", html)
        self.assertNotIn("equivalente a", html)
        self.assertNotIn("tasa BCV", html)

    def test_23b_amounts_with_the_bolivar_as_company_currency(self):
        """Company in bolivars, alternate currency USD: the bolivar amount
        comes first and the rate is `foreign_rate` (bolivars per USD)."""
        vef = self.company.currency_id
        usd = self.env.ref("base.USD")
        amounts = self.env["account.move"]._compute_donation_amounts(
            vef, usd, 38000.0, 84.44, 450.0, 0.0022222
        )
        self.assertEqual(amounts["currency"], vef)
        self.assertEqual(amounts["amount"], 38000.0)
        self.assertEqual(amounts["equivalent_currency"], usd)
        self.assertEqual(amounts["equivalent_amount"], 84.44)
        self.assertEqual(amounts["rate"], 450.0)

    def test_23c_amounts_with_the_bolivar_as_alternate_currency(self):
        """Company in USD, alternate currency the bolivar (Higea): the
        bolivar amount still comes first and the rate is the company rate
        (`foreign_inverse_rate`: bolivars per USD), not the inverse one."""
        vef = self.company.currency_id
        usd = self.env.ref("base.USD")
        amounts = self.env["account.move"]._compute_donation_amounts(
            usd, vef, 84.44, 38000.0, 0.0022222, 450.0
        )
        self.assertEqual(amounts["currency"], vef)
        self.assertEqual(amounts["amount"], 38000.0)
        self.assertEqual(amounts["equivalent_currency"], usd)
        self.assertEqual(amounts["equivalent_amount"], 84.44)
        self.assertEqual(amounts["rate"], 450.0)

    def test_23d_amounts_without_alternate_amount_or_rate(self):
        vef = self.company.currency_id
        usd = self.env.ref("base.USD")
        Move = self.env["account.move"]
        for args in (
            (vef, False, 100.0, 0.0, 0.0, 0.0),
            (vef, vef, 100.0, 100.0, 1.0, 1.0),
            (vef, usd, 100.0, 0.0, 450.0, 0.0022),
            (vef, usd, 100.0, 0.22, 0.0, 0.0),
            (usd, vef, 0.22, 100.0, 0.0, 0.0),
        ):
            with self.subTest(args=args):
                amounts = Move._compute_donation_amounts(*args)
                self.assertFalse(amounts["equivalent_currency"])
                self.assertEqual(amounts["rate"], 0.0)

    def test_24_manual_entry_is_not_a_stock_valuation_entry(self):
        move = self.env["account.move"].create(self._entry_vals())
        move.with_context(move_action_post_alert=True).action_post()
        self.assertFalse(move.is_stock_valuation_entry)
        action = move.print_donation_certificate()
        self.assertIsInstance(action, dict)
